import { ReactNode } from 'react';

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
        justifyContent: 'flex-start',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '640px',
          padding: '48px 24px 0',
        }}
      >
        {children}
      </div>
    </div>
  );
}
