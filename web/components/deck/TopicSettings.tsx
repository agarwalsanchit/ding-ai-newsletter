'use client';

import { motion, AnimatePresence } from 'framer-motion';

interface TopicSettingsProps {
  open: boolean;
  topics: string[];
  isSelected: (topic: string) => boolean;
  onToggle: (topic: string) => void;
  onSelectAll: () => void;
  onClose: () => void;
  activeCount: number;
}

function stripEmoji(topic: string): string {
  return topic.split(' ').slice(1).join(' ');
}

export default function TopicSettings({
  open,
  topics,
  isSelected,
  onToggle,
  onSelectAll,
  onClose,
  activeCount,
}: TopicSettingsProps) {
  const allSelected = activeCount === topics.length;

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="settings-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0,0,0,0.5)',
              zIndex: 60,
            }}
          />

          <motion.div
            key="settings-sheet"
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 30, stiffness: 300 }}
            style={{
              position: 'fixed',
              bottom: 0,
              left: 0,
              right: 0,
              backgroundColor: 'var(--surface)',
              borderRadius: '16px 16px 0 0',
              zIndex: 61,
              padding: '20px 24px max(env(safe-area-inset-bottom), 32px)',
            }}
          >
            {/* Header */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '24px',
              }}
            >
              <div>
                <p
                  style={{
                    fontFamily: 'var(--font-sans)',
                    fontSize: '18px',
                    fontWeight: 600,
                    color: 'var(--text)',
                  }}
                >
                  Topics
                </p>
                <p
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '10px',
                    letterSpacing: '0.06em',
                    color: 'var(--muted)',
                    marginTop: '2px',
                  }}
                >
                  {activeCount} of {topics.length} selected
                </p>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                {!allSelected && (
                  <button
                    onClick={onSelectAll}
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '10px',
                      letterSpacing: '0.06em',
                      textTransform: 'uppercase',
                      color: 'var(--accent)',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      padding: '4px',
                    }}
                  >
                    Select all
                  </button>
                )}
                <button
                  onClick={onClose}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'var(--muted)',
                    padding: '4px',
                    display: 'flex',
                    alignItems: 'center',
                  }}
                  aria-label="Close settings"
                >
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path
                      d="M2 2L14 14M14 2L2 14"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                    />
                  </svg>
                </button>
              </div>
            </div>

            {/* Topic list */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {topics.map((topic) => {
                const active = isSelected(topic);
                return (
                  <button
                    key={topic}
                    onClick={() => onToggle(topic)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '12px 0',
                      background: 'none',
                      border: 'none',
                      borderBottom: '1px solid var(--divider)',
                      cursor: 'pointer',
                      width: '100%',
                      textAlign: 'left',
                    }}
                  >
                    <span
                      style={{
                        fontFamily: 'var(--font-sans)',
                        fontSize: '15px',
                        color: active ? 'var(--text)' : 'var(--muted)',
                      }}
                    >
                      {topic}
                    </span>

                    {/* Checkbox */}
                    <div
                      style={{
                        width: '20px',
                        height: '20px',
                        borderRadius: '50%',
                        border: active ? 'none' : '1.5px solid var(--divider)',
                        backgroundColor: active ? 'var(--accent)' : 'transparent',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        transition: 'background-color 0.15s',
                      }}
                    >
                      {active && (
                        <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                          <path
                            d="M1 4L3.5 6.5L9 1"
                            stroke="white"
                            strokeWidth="1.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
