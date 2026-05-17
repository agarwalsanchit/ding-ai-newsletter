'use client';

import { useState } from 'react';
import { AnimatePresence, motion, PanInfo } from 'framer-motion';
import { DailyBrief, ApprovedArticle } from '@/lib/types';
import BriefCard from './BriefCard';
import ArticleCard from './ArticleCard';
import EndCard from './EndCard';

const SWIPE_THRESHOLD = 80;
const VELOCITY_THRESHOLD = 500;

const variants = {
  enter: (dir: number) => ({
    y: dir > 0 ? '100vh' : '-100vh',
    opacity: 0,
  }),
  center: {
    y: 0,
    opacity: 1,
  },
  exit: (dir: number) => ({
    y: dir > 0 ? '-100vh' : '100vh',
    opacity: 0,
  }),
};

const transition = { duration: 0.3, ease: 'easeOut' as const };

interface DeckProps {
  brief: DailyBrief | null;
  articles: ApprovedArticle[];
}

export default function Deck({ brief, articles }: DeckProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [direction, setDirection] = useState(1);

  // total cards: brief + articles + end
  const totalCards = 1 + articles.length + 1;

  const handleDragEnd = (
    _: MouseEvent | TouchEvent | PointerEvent,
    info: PanInfo
  ) => {
    const { offset, velocity } = info;

    if (offset.y < -SWIPE_THRESHOLD || velocity.y < -VELOCITY_THRESHOLD) {
      // Swipe up → next card
      if (currentIndex < totalCards - 1) {
        setDirection(1);
        setCurrentIndex((prev) => prev + 1);
      }
    } else if (offset.y > SWIPE_THRESHOLD || velocity.y > VELOCITY_THRESHOLD) {
      // Swipe down → previous card
      if (currentIndex > 0) {
        setDirection(-1);
        setCurrentIndex((prev) => prev - 1);
      }
    }
  };

  const renderCard = (index: number) => {
    if (index === 0) return <BriefCard brief={brief} />;
    if (index <= articles.length) return <ArticleCard article={articles[index - 1]} />;
    return <EndCard />;
  };

  return (
    <div style={{ overflow: 'hidden', height: '100dvh', width: '100%' }}>
      <AnimatePresence mode="wait" custom={direction}>
        <motion.div
          key={currentIndex}
          custom={direction}
          variants={variants}
          initial="enter"
          animate="center"
          exit="exit"
          transition={transition}
          drag="y"
          dragConstraints={{ top: 0, bottom: 0 }}
          dragElastic={0.1}
          onDragEnd={handleDragEnd}
          style={{ height: '100dvh', width: '100%' }}
        >
          {renderCard(currentIndex)}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
