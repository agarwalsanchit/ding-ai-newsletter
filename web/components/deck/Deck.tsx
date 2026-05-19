'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence, PanInfo } from 'framer-motion';
import { DailyBrief, ApprovedArticle, TranslationMap } from '@/lib/types';
import { useLanguage } from '@/lib/hooks/useLanguage';
import { useTopicPrefs } from '@/lib/hooks/useTopicPrefs';
import BriefCard from './BriefCard';
import ArticleCard from './ArticleCard';
import EndCard from './EndCard';
import DetailView from './DetailView';
import TopicSettings from './TopicSettings';
import SplashScreen from './SplashScreen';

const SWIPE_THRESHOLD = 80;
const VELOCITY_THRESHOLD = 500;

interface DeckProps {
  brief: DailyBrief | null;
  articles: ApprovedArticle[];
  translations: TranslationMap;
}

function readHashIndex(): number {
  if (typeof window === 'undefined') return 0;
  const m = window.location.hash.match(/^#card-(\d+)$/);
  if (!m) return 0;
  return parseInt(m[1], 10);
}

export default function Deck({ brief, articles, translations }: DeckProps) {
  // Phase 4: topic filtering
  const allTopics = useMemo(
    () => [...new Set(articles.map((a) => a.topic))],
    [articles]
  );
  const { isSelected, toggle: toggleTopic, selectAll, activeCount } = useTopicPrefs(allTopics);

  const visibleArticles = useMemo(
    () => articles.filter((a) => isSelected(a.topic)),
    [articles, isSelected]
  );

  const totalCards = 1 + visibleArticles.length + 1;

  const [currentIndex, setCurrentIndex] = useState(0);
  const [direction, setDirection] = useState<1 | -1>(1);
  const [detailArticle, setDetailArticle] = useState<ApprovedArticle | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Splash: show once per browser session
  const [showSplash, setShowSplash] = useState(() => {
    if (typeof window === 'undefined') return false;
    const seen = sessionStorage.getItem('ding_splash_seen');
    return !seen;
  });

  // Phase 2: language
  const { lang, toggle: toggleLang } = useLanguage();

  // Restore position from URL hash
  useEffect(() => {
    const idx = readHashIndex();
    if (idx > 0 && idx < totalCards) setCurrentIndex(idx);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Clamp index if topic filter reduces deck size
  useEffect(() => {
    if (currentIndex >= totalCards) {
      setCurrentIndex(Math.max(0, totalCards - 1));
    }
  }, [currentIndex, totalCards]);

  // Sync URL hash
  useEffect(() => {
    const hash = currentIndex === 0 ? '' : `#card-${currentIndex}`;
    window.history.replaceState(null, '', hash || window.location.pathname);
  }, [currentIndex]);

  const goTo = useCallback(
    (next: number) => {
      if (next < 0 || next >= totalCards) return;
      setDirection(next > currentIndex ? 1 : -1);
      setCurrentIndex(next);
    },
    [currentIndex, totalCards]
  );

  const handleDragEnd = useCallback(
    (_: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
      if (detailArticle || settingsOpen) return;
      const { offset, velocity } = info;
      if (offset.y < -SWIPE_THRESHOLD || velocity.y < -VELOCITY_THRESHOLD) goTo(currentIndex + 1);
      if (offset.y >  SWIPE_THRESHOLD || velocity.y >  VELOCITY_THRESHOLD) goTo(currentIndex - 1);
    },
    [currentIndex, detailArticle, settingsOpen, goTo]
  );

  const openDetail    = useCallback((a: ApprovedArticle) => setDetailArticle(a), []);
  const closeDetail   = useCallback(() => setDetailArticle(null), []);
  const dismissSplash = useCallback(() => {
    sessionStorage.setItem('ding_splash_seen', '1');
    setShowSplash(false);
  }, []);

  const renderCard = (index: number) => {
    if (index === 0) {
      return <BriefCard brief={brief} onOpenSettings={() => setSettingsOpen(true)} />;
    }
    if (index <= visibleArticles.length) {
      const article = visibleArticles[index - 1];
      return (
        <ArticleCard
          article={article}
          translation={translations[article.id] ?? null}
          lang={lang}
          onToggleLang={toggleLang}
          onOpenDetail={() => openDetail(article)}
        />
      );
    }
    return <EndCard />;
  };

  const variants = {
    enter: (dir: number) => ({ y: dir > 0 ? '100%' : '-100%' }),
    center: {
      y: 0,
      transition: {
        type: 'tween' as const,
        duration: 0.38,
        ease: [0.25, 0.1, 0.25, 1] as [number, number, number, number],
      },
    },
    exit: (dir: number) => ({
      y: dir > 0 ? '-100%' : '100%',
      transition: { type: 'tween' as const, duration: 0.15, ease: 'easeIn' as const },
    }),
  };

  return (
    <>
      {showSplash && <SplashScreen onDone={dismissSplash} />}

      <div style={{ position: 'relative', overflow: 'hidden', height: '100dvh', width: '100%' }}>
        <AnimatePresence initial={false} custom={direction} mode="wait">
          <motion.div
            key={currentIndex}
            custom={direction}
            variants={variants}
            initial="enter"
            animate="center"
            exit="exit"
            drag="y"
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{
              top:    currentIndex < totalCards - 1 ? 0.15 : 0.04,
              bottom: currentIndex > 0              ? 0.15 : 0.04,
            }}
            whileDrag={{ scale: 0.98 }}
            onDragEnd={handleDragEnd}
            style={{ position: 'absolute', inset: 0, height: '100dvh', width: '100%' }}
          >
            {renderCard(currentIndex)}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Phase 2 + 3: Detail view */}
      <DetailView
        article={detailArticle}
        translation={detailArticle ? (translations[detailArticle.id] ?? null) : null}
        lang={lang}
        onToggleLang={toggleLang}
        onClose={closeDetail}
      />

      {/* Phase 4: Topic settings */}
      <TopicSettings
        open={settingsOpen}
        topics={allTopics}
        isSelected={isSelected}
        onToggle={toggleTopic}
        onSelectAll={selectAll}
        onClose={() => setSettingsOpen(false)}
        activeCount={activeCount}
      />
    </>
  );
}
