'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Image from 'next/image';

const HOLD_MS  = 2600; // how long the splash shows before auto-fading
const FADE_MS  = 600;  // exit fade duration

interface Props {
  onDone: () => void;
}

export default function SplashScreen({ onDone }: Props) {
  const [exiting, setExiting] = useState(false);

  const dismiss = () => {
    if (exiting) return;
    setExiting(true);
    setTimeout(onDone, FADE_MS);
  };

  useEffect(() => {
    const t = setTimeout(dismiss, HOLD_MS);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AnimatePresence>
      {!exiting && (
        <motion.div
          key="splash"
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: FADE_MS / 1000, ease: 'easeOut' }}
          onClick={dismiss}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 200,
            backgroundColor: 'var(--bg)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            userSelect: 'none',
            paddingBottom: 'env(safe-area-inset-bottom, 0px)',
          }}
        >
          {/* Icon */}
          <motion.div
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.7, ease: [0.34, 1.1, 0.64, 1] }}
          >
            <Image
              src="/icon-192x192.png"
              alt="DING News"
              width={72}
              height={72}
              style={{ borderRadius: '18px' }}
              priority
            />
          </motion.div>

          {/* Wordmark */}
          <motion.h1
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.45, ease: 'easeOut' }}
            style={{
              fontFamily: 'var(--font-sans)',
              fontSize: '34px',
              fontWeight: 700,
              letterSpacing: '-0.025em',
              marginTop: '18px',
              marginBottom: 0,
              lineHeight: 1,
            }}
          >
            DING{' '}
            <span style={{ color: 'var(--accent)' }}>News</span>
          </motion.h1>

          {/* Subheader */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.55 }}
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              letterSpacing: '0.2em',
              textTransform: 'uppercase',
              color: 'var(--muted)',
              marginTop: '14px',
            }}
          >
            Signal Over Noise
          </motion.p>

          {/* Tagline */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.55, delay: 0.9 }}
            style={{
              fontFamily: 'var(--font-sans)',
              fontSize: '14px',
              color: 'var(--subtle)',
              marginTop: '28px',
              textAlign: 'center',
              lineHeight: 1.55,
              maxWidth: '240px',
            }}
          >
            Unbiased, high-impact news.
            <br />
            Your 10-minute morning ritual.
          </motion.p>

          {/* Tap-to-skip hint */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4, delay: 1.5 }}
            style={{
              position: 'absolute',
              bottom: 'calc(env(safe-area-inset-bottom, 0px) + 32px)',
              fontFamily: 'var(--font-mono)',
              fontSize: '10px',
              letterSpacing: '0.12em',
              color: 'var(--subtle)',
            }}
          >
            tap to continue
          </motion.p>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
