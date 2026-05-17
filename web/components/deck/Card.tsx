import { ReactNode } from 'react';

export default function Card({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        height: '100dvh',
        width: '100%',
        overflow: 'hidden',
        backgroundColor: 'var(--bg)',
        color: 'var(--text)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '640px',
          padding: '0 24px',
        }}
      >
        {children}
      </div>
    </div>
  );
}
