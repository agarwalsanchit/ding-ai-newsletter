import React, { ReactNode } from 'react';

export default function Card({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        position: 'relative',
        height: '100dvh',
        width: '100%',
        overflow: 'hidden',
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
          flex: 1,
          overflowY: 'auto',
          // Top: safe-area for notch + breathing room
          // Bottom: 88px so content doesn't hide behind the swipe affordance
          padding: 'calc(env(safe-area-inset-top, 0px) + 44px) 28px 88px',
          WebkitOverflowScrolling: 'touch' as React.CSSProperties['WebkitOverflowScrolling'],
        }}
      >
        {children}
      </div>
    </div>
  );
}
