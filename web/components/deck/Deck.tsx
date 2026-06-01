'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence, PanInfo, useReducedMotion } from 'framer-motion';
import { track } from '@vercel/analytics';
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
  loadError?: boolean;
}

function readHashIndex(): number {
  if (typeof window === 'undefined') return 0;
  const m = window.location.hash.match(/^#card-(\d+)$/);
  if (!m) return 0;
  return parseInt(m[1], 10);
}

export default function Deck({ brief, articles, translations, loadError = false }: DeckProps) {
  const reduceMotion = useReducedMotion();
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

  // Topics present in today's deck, in first-appearance order — drives the
  // tappable chips on the brief card.
  const deckTopics = useMemo(() => {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const a of visibleArticles) {
      if (!seen.has(a.topic)) {
        seen.add(a.topic);
        out.push(a.topic);
      }
    }
    return out;
  }, [visibleArticles]);

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

  // Beta signal: did the reader make it all the way to the end card?
  useEffect(() => {
    if (totalCards > 1 && currentIndex === totalCards - 1) {
      track('deck_complete');
    }
  }, [currentIndex, totalCards]);

  const goTo = useCallback(
    (next: number) => {
      if (next < 0 || next >= totalCards) return;
      setDirection(next > currentIndex ? 1 : -1);
      setCurrentIndex(next);
    },
    [currentIndex, totalCards]
  );

  // Tap a brief-card chip → jump to that topic's first story (card index is
  // 1-based: card 0 is the brief, so article i lives at i + 1).
  const jumpToTopic = useCallback(
    (topic: string) => {
      const idx = visibleArticles.findIndex((a) => a.topic === topic);
      if (idx >= 0) {
        track('topic_jump', { topic });
        goTo(idx + 1);
      }
    },
    [visibleArticles, goTo]
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

  // Mirror overlay state into refs so the once-bound popstate handler always
  // sees the latest values without re-subscribing.
  const detailRef = useRef(detailArticle);
  const settingsRef = useRef(settingsOpen);
  useEffect(() => { detailRef.current = detailArticle; }, [detailArticle]);
  useEffect(() => { settingsRef.current = settingsOpen; }, [settingsOpen]);

  // Hardware/browser back button: close an open overlay instead of leaving the
  // app. Opening an overlay pushes a history entry; back pops it and we close.
  useEffect(() => {
    const onPop = () => {
      if (detailRef.current) setDetailArticle(null);
      else if (settingsRef.current) setSettingsOpen(false);
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const openDetail = useCallback((a: ApprovedArticle) => {
    window.history.pushState({ overlay: 'detail' }, '');
    track('detail_open', { topic: a.topic });
    setDetailArticle(a);
  }, []);
  // Programmatic close (X, backdrop, swipe-down, Esc): pop the pushed entry so
  // the history stack stays balanced. If we got here via the back button the
  // entry is already gone, so just clear state.
  const closeDetail = useCallback(() => {
    if (window.history.state?.overlay === 'detail') window.history.back();
    else setDetailArticle(null);
  }, []);
  const openSettings = useCallback(() => {
    window.history.pushState({ overlay: 'settings' }, '');
    setSettingsOpen(true);
  }, []);
  const closeSettings = useCallback(() => {
    if (window.history.state?.overlay === 'settings') window.history.back();
    else setSettingsOpen(false);
  }, []);
  const dismissSplash = useCallback(() => {
    sessionStorage.setItem('ding_splash_seen', '1');
    setShowSplash(false);
  }, []);

  const renderCard = (index: number) => {
    if (index === 0) {
      return <BriefCard brief={brief} articleCount={visibleArticles.length} loadError={loadError} topics={deckTopics} onJumpToTopic={jumpToTopic} onOpenSettings={openSettings} />;
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

  // Reduced-motion: cross-fade in place instead of sliding/springing.
  const variants = reduceMotion
    ? {
        enter: () => ({ opacity: 0 }),
        center: { opacity: 1, transition: { duration: 0.2 } },
        exit: () => ({ opacity: 0, transition: { duration: 0.15 } }),
      }
    : {
        enter: (dir: number) => ({ y: dir > 0 ? '100%' : '-100%' }),
        center: {
          y: 0,
          transition: {
            type: 'spring' as const,
            stiffness: 340,
            damping: 34,
            mass: 0.85,
          },
        },
        exit: (dir: number) => ({
          y: dir > 0 ? '-100%' : '100%',
          transition: {
            type: 'tween' as const,
            duration: 0.3,
            ease: [0.4, 0, 0.2, 1] as [number, number, number, number],
          },
        }),
      };

  // Deck progress: 0 at the brief, 1 at the end card. Drives the top bar so the
  // reader always knows how far through the morning deck they are.
  const progress = totalCards > 1 ? currentIndex / (totalCards - 1) : 0;

  return (
    <>
      {showSplash && <SplashScreen onDone={dismissSplash} />}

      {/* Top progress bar */}
      <div
        aria-hidden
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          height: 'calc(env(safe-area-inset-top, 0px) + 3px)',
          background: 'var(--divider)',
          zIndex: 40,
          pointerEvents: 'none',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${Math.round(progress * 100)}%`,
            background: 'var(--accent)',
            transition: 'width 0.38s cubic-bezier(0.25, 0.1, 0.25, 1)',
          }}
        />
      </div>

      <div style={{ position: 'relative', overflow: 'hidden', height: '100dvh', width: '100%' }}>
        <AnimatePresence initial={false} custom={direction}>
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
            style={{ position: 'absolute', inset: 0, height: '100dvh', width: '100%', touchAction: 'none' }}
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
        onClose={closeSettings}
        activeCount={activeCount}
      />
    </>
  );
}
