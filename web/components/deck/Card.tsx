import { ReactNode } from 'react';

export default function Card({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        position: 'relative',
        height: '100dvh',
        width: '100%',
        overflow: 'hidden',          // must NOT scroll — kills swipe gesture
        backgroundColor: 'var(--bg)',
        color: 'var(--text)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '640px',
          // Top: safe-area + breathing room. Bottom: 72px clears the affordance.
          padding: 'calc(env(safe-area-inset-top, 0px) + 44px) 28px 72px',
          overflow: 'hidden',        // clip, never scroll
        }}
      >
        {children}
      </div>
    </div>
  );
}
