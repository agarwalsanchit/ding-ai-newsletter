'use client';

import { useState } from 'react';
import { motion, AnimatePresence, PanInfo } from 'framer-motion';
import { DailyBrief, ApprovedArticle } from '@/lib/types';
import BriefCard from './BriefCard';
import ArticleCard from './ArticleCard';
import EndCard from './EndCard';

const SWIPE_THRESHOLD = 80;
const VELOCITY_THRESHOLD = 500;

interface DeckProps {
  brief: DailyBrief | null;
  articles: ApprovedArticle[];
}

export default function Deck({ brief, articles }: DeckProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [direction, setDirection] = useState<1 | -1>(1); // 1 = going forward, -1 = going back

  const totalCards = 1 + articles.length + 1;

  const renderCard = (index: number) => {
    if (index === 0) return <BriefCard brief={brief} />;
    if (index <= articles.length) return <ArticleCard article={articles[index - 1]} />;
    return <EndCard />;
  };

  const handleDragEnd = (
    _: MouseEvent | TouchEvent | PointerEvent,
    info: PanInfo
  ) => {
    const { offset, velocity } = info;
    const swipeUp   = offset.y < -SWIPE_THRESHOLD || velocity.y < -VELOCITY_THRESHOLD;
    const swipeDown = offset.y >  SWIPE_THRESHOLD || velocity.y >  VELOCITY_THRESHOLD;

    if (swipeUp && currentIndex < totalCards - 1) {
      setDirection(1);
      setCurrentIndex((prev) => prev + 1);
    } else if (swipeDown && currentIndex > 0) {
      setDirection(-1);
      setCurrentIndex((prev) => prev - 1);
    }
  };

  const variants = {
    enter: (dir: number) => ({
      y: dir > 0 ? '100%' : '-100%',
    }),
    center: {
      y: 0,
      transition: { type: 'tween' as const, duration: 0.38, ease: [0.25, 0.1, 0.25, 1] as [number, number, number, number] },
    },
    exit: (dir: number) => ({
      y: dir > 0 ? '-100%' : '100%',
      transition: { type: 'tween' as const, duration: 0.15, ease: 'easeIn' as const },
    }),
  };

  return (
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
          dragElastic={0.15}
          whileDrag={{ scale: 0.98 }}
          onDragEnd={handleDragEnd}
          style={{ position: 'absolute', inset: 0, height: '100dvh', width: '100%' }}
        >
          {renderCard(currentIndex)}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
