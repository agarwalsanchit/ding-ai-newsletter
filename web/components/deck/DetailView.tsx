'use client';

import { useEffect, useRef } from 'react';
import { motion, AnimatePresence, PanInfo } from 'framer-motion';
import { ApprovedArticle, Translation } from '@/lib/types';
import { Language } from '@/lib/hooks/useLanguage';
import LanguageToggle from './LanguageToggle';
import ShareButton from './ShareButton';

function extractDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

interface DetailViewProps {
  article: ApprovedArticle | null;
  translation: Translation | null;
  lang: Language;
  onToggleLang: () => void;
  onClose: () => void;
}

export default function DetailView({
  article,
  translation,
  lang,
  onToggleLang,
  onClose,
}: DetailViewProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (article && scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [article]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const handleDragEnd = (_: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    if (info.offset.y > 80 || info.velocity.y > 500) {
      onClose();
    }
  };

  const hasTranslation = !!translation?.title_translated;
  const showHindi = lang === 'hi' && hasTranslation;

  const title   = showHindi ? translation!.title_translated!                       : article?.title ?? '';
  const detail  = showHindi
    ? (translation!.detail_summary_translated ?? article?.detail_summary ?? article?.balanced_summary ?? '')
    : (article?.detail_summary ?? article?.balanced_summary ?? '');
  const wim     = showHindi ? (translation!.why_it_matters_translated ?? article?.why_it_matters ?? '') : (article?.why_it_matters ?? '');

  // Phase 3 perspectives
  const hasPerspectives = !!(article?.left_perspective && article?.right_perspective);

  return (
    <AnimatePresence>
      {article && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0,0,0,0.6)',
              zIndex: 50,
            }}
          />

          {/* Sheet */}
          <motion.div
            key="sheet"
            drag="y"
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0, bottom: 0.3 }}
            onDragEnd={handleDragEnd}
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 30, stiffness: 300 }}
            style={{
              position: 'fixed',
              bottom: 0,
              left: 0,
              right: 0,
              height: '88dvh',
              backgroundColor: 'var(--surface)',
              borderRadius: '16px 16px 0 0',
              zIndex: 51,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
          >
            {/* Handle + close row */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '12px 20px 8px',
                position: 'relative',
                flexShrink: 0,
              }}
            >
              <div
                style={{
                  width: '36px',
                  height: '4px',
                  borderRadius: '2px',
                  background: 'var(--divider)',
                }}
              />
              {/* Language toggle — only if translation exists */}
              {hasTranslation && (
                <div style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)' }}>
                  <LanguageToggle lang={lang} onToggle={onToggleLang} />
                </div>
              )}
              <div
                style={{
                  position: 'absolute',
                  right: '44px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                }}
              >
                <ShareButton title={article.title} url={article.source_urls[0]} />
              </div>
              <button
                onClick={onClose}
                style={{
                  position: 'absolute',
                  right: '16px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--muted)',
                  padding: '8px',
                  display: 'flex',
                  alignItems: 'center',
                }}
                aria-label="Close"
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M2 2L14 14M14 2L2 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </button>
            </div>

            {/* Scrollable content */}
            <div
              ref={scrollRef}
              onPointerDownCapture={(e) => e.stopPropagation()}
              style={{
                flex: 1,
                overflowY: 'auto',
                WebkitOverflowScrolling: 'touch',
                padding: '8px 24px max(env(safe-area-inset-bottom), 32px)',
              } as React.CSSProperties}
            >
              {/* Topic + source */}
              <p
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '11px',
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  color: 'var(--muted)',
                  marginBottom: '16px',
                }}
              >
                {article.topic.split(' ').slice(1).join(' ')}
                {article.source_urls[0] && (
                  <>
                    {' · '}
                    <a
                      href={article.source_urls[0]}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: 'var(--accent)', textDecoration: 'none' }}
                    >
                      {extractDomain(article.source_urls[0])}
                    </a>
                  </>
                )}
              </p>

              {/* Headline */}
              <h2
                style={{
                  fontFamily: 'var(--font-sans)',
                  fontSize: 'clamp(20px, 5vw, 26px)',
                  fontWeight: 600,
                  lineHeight: 1.15,
                  letterSpacing: '-0.02em',
                  marginBottom: '24px',
                }}
              >
                {title}
              </h2>

              {/* Detail body */}
              <p
                style={{
                  fontFamily: 'var(--font-sans)',
                  fontSize: '16px',
                  lineHeight: 1.6,
                  color: 'var(--text)',
                  marginBottom: '24px',
                }}
              >
                {detail}
              </p>

              {/* Why it matters */}
              <div
                style={{
                  borderLeft: '2px solid var(--accent)',
                  paddingLeft: '14px',
                  marginBottom: hasPerspectives ? '32px' : '0',
                }}
              >
                <p
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '10px',
                    letterSpacing: '0.08em',
                    textTransform: 'uppercase',
                    color: 'var(--accent)',
                    marginBottom: '6px',
                  }}
                >
                  {showHindi ? 'यह क्यों मायने रखता है' : 'Why it matters'}
                </p>
                <p
                  style={{
                    fontFamily: 'var(--font-sans)',
                    fontSize: '15px',
                    lineHeight: 1.55,
                    color: 'var(--text)',
                  }}
                >
                  {wim}
                </p>
              </div>

              {/* Phase 3: Perspectives */}
              {hasPerspectives && (
                <div
                  style={{
                    borderTop: '1px solid var(--divider)',
                    paddingTop: '24px',
                    marginBottom: '24px',
                  }}
                >
                  <p
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '10px',
                      letterSpacing: '0.08em',
                      textTransform: 'uppercase',
                      color: 'var(--subtle)',
                      marginBottom: '16px',
                    }}
                  >
                    Perspectives
                  </p>

                  {/* Left-leaning */}
                  <div style={{ marginBottom: '16px' }}>
                    <p
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '10px',
                        letterSpacing: '0.08em',
                        textTransform: 'uppercase',
                        color: 'var(--accent)',
                        marginBottom: '8px',
                      }}
                    >
                      Progressive
                    </p>
                    <p
                      style={{
                        fontFamily: 'var(--font-sans)',
                        fontSize: '14px',
                        lineHeight: 1.55,
                        color: 'var(--text)',
                      }}
                    >
                      {article.left_perspective}
                    </p>
                  </div>

                  {/* Right-leaning */}
                  <div>
                    <p
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '10px',
                        letterSpacing: '0.08em',
                        textTransform: 'uppercase',
                        color: 'var(--muted)',
                        marginBottom: '8px',
                      }}
                    >
                      Conservative
                    </p>
                    <p
                      style={{
                        fontFamily: 'var(--font-sans)',
                        fontSize: '14px',
                        lineHeight: 1.55,
                        color: 'var(--text)',
                      }}
                    >
                      {article.right_perspective}
                    </p>
                  </div>
                </div>
              )}

              {/* Sources */}
              {article.source_urls.length > 0 && (
                <div style={{ borderTop: '1px solid var(--divider)', paddingTop: '20px' }}>
                  <p
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '10px',
                      letterSpacing: '0.08em',
                      textTransform: 'uppercase',
                      color: 'var(--subtle)',
                      marginBottom: '12px',
                    }}
                  >
                    Sources
                  </p>
                  {article.source_urls.map((url) => (
                    <a
                      key={url}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        display: 'block',
                        fontFamily: 'var(--font-mono)',
                        fontSize: '12px',
                        color: 'var(--accent)',
                        textDecoration: 'none',
                        marginBottom: '8px',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {extractDomain(url)}
                    </a>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
