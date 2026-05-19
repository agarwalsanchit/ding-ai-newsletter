import { Language } from '@/lib/hooks/useLanguage';

interface LanguageToggleProps {
  lang: Language;
  onToggle: () => void;
}

export default function LanguageToggle({ lang, onToggle }: LanguageToggleProps) {
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        onToggle();
      }}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '2px',
        background: 'none',
        border: '1px solid var(--divider)',
        borderRadius: '999px',
        padding: '3px 2px',
        cursor: 'pointer',
        flexShrink: 0,
      }}
      aria-label={`Switch to ${lang === 'en' ? 'Hindi' : 'English'}`}
    >
      {(['en', 'hi'] as Language[]).map((l) => (
        <span
          key={l}
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '9px',
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            padding: '2px 7px',
            borderRadius: '999px',
            backgroundColor: lang === l ? 'var(--accent)' : 'transparent',
            color: lang === l ? '#fff' : 'var(--muted)',
            transition: 'background-color 0.15s, color 0.15s',
          }}
        >
          {l}
        </span>
      ))}
    </button>
  );
}
