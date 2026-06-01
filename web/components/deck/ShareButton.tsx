'use client';

import { useState } from 'react';

interface ShareButtonProps {
  title: string;
  url?: string;
  size?: number;
}

// Share via the native Web Share API when available (mobile), with a
// clipboard-copy fallback on desktop browsers that lack it.
export default function ShareButton({ title, url, size = 16 }: ShareButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleShare = async (e: React.MouseEvent | React.KeyboardEvent) => {
    e.stopPropagation();
    const shareUrl =
      url || (typeof window !== 'undefined' ? window.location.href : '');
    const data: ShareData = { title: 'DING News', text: title, url: shareUrl };

    if (typeof navigator !== 'undefined' && navigator.share) {
      try {
        await navigator.share(data);
      } catch {
        // user cancelled or the share sheet failed — nothing to do
      }
      return;
    }

    // Fallback: copy headline + link to clipboard
    try {
      await navigator.clipboard.writeText(`${title} — ${shareUrl}`.trim());
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard blocked — silently no-op
    }
  };

  return (
    <button
      onClick={handleShare}
      onKeyDown={(e) => {
        if (e.key === 'Enter') handleShare(e);
      }}
      aria-label="Share"
      style={{
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        color: copied ? 'var(--accent)' : 'var(--muted)',
        padding: '6px',
        display: 'flex',
        alignItems: 'center',
        gap: '5px',
      }}
    >
      {copied ? (
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '10px',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
          }}
        >
          Copied
        </span>
      ) : (
        <svg
          width={size}
          height={size}
          viewBox="0 0 16 16"
          fill="none"
          aria-hidden
        >
          {/* upward share arrow + tray */}
          <path
            d="M8 1.5v8M8 1.5L5.2 4.3M8 1.5l2.8 2.8"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M3 7.5v5.5a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V7.5"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      )}
    </button>
  );
}
