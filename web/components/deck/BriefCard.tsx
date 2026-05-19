import { DailyBrief } from '@/lib/types';
import Card from './Card';

function formatBriefDate(dateStr: string): string {
  const [year, month, day] = dateStr.split('-').map(Number);
  const d = new Date(year, month - 1, day);
  const weekday = d.toLocaleDateString('en-US', { weekday: 'long' }).toUpperCase();
  const monthName = d.toLocaleDateString('en-US', { month: 'long' }).toUpperCase();
  return `${weekday}, ${monthName} ${day}`;
}

interface BriefCardProps {
  brief: DailyBrief | null;
  onOpenSettings: () => void;
}

export default function BriefCard({ brief, onOpenSettings }: BriefCardProps) {
  const dateLabel = brief
    ? formatBriefDate(brief.brief_date)
    : new Date().toLocaleDateString('en-US', {
        weekday: 'long',
        month: 'long',
        day: 'numeric',
      }).toUpperCase();

  return (
    <Card>
      {/* Gear icon — Phase 4 topic filter */}
      <div
        style={{
          position: 'absolute',
          top: '20px',
          right: '20px',
          zIndex: 10,
        }}
      >
        <button
          onClick={onOpenSettings}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--subtle)',
            padding: '8px',
            display: 'flex',
            alignItems: 'center',
          }}
          aria-label="Topic settings"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <circle cx="9" cy="9" r="2.5" stroke="currentColor" strokeWidth="1.4" />
            <path
              d="M9 1.5v1.2M9 15.3v1.2M1.5 9h1.2M15.3 9h1.2M3.6 3.6l.85.85M13.55 13.55l.85.85M14.4 3.6l-.85.85M4.45 13.55l-.85.85"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
            />
          </svg>
        </button>
      </div>

      {/* Branding */}
      <p
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '10px',
          letterSpacing: '0.18em',
          textTransform: 'uppercase',
          color: 'var(--accent)',
          marginBottom: '6px',
        }}
      >
        DING News
      </p>

      {/* Date */}
      <p
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '10px',
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          color: 'var(--subtle)',
          marginBottom: '20px',
        }}
      >
        {dateLabel}
      </p>

      {/* Editorial opener */}
      <h1
        style={{
          fontFamily: 'var(--font-sans)',
          fontSize: '28px',
          fontWeight: 600,
          lineHeight: 1.1,
          letterSpacing: '-0.02em',
          marginBottom: '16px',
        }}
      >
        {brief ? brief.editorial_opener : 'Good morning.'}
      </h1>

      {/* Brief body */}
      <p
        style={{
          fontFamily: 'var(--font-sans)',
          fontSize: '16px',
          lineHeight: 1.6,
          color: 'var(--text)',
          marginBottom: '16px',
        }}
      >
        {brief ? brief.brief_body : ''}
      </p>

      {/* Transition line */}
      <p
        style={{
          fontFamily: 'var(--font-sans)',
          fontSize: '14px',
          lineHeight: 1.5,
          color: 'var(--muted)',
          marginBottom: '24px',
        }}
      >
        {brief ? brief.transition_line : ''}
      </p>

      {/* Topic chips */}
      {brief && brief.topic_chips.length > 0 && (
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '7px',
          }}
        >
          {brief.topic_chips.map((chip) => (
            <span
              key={chip}
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '9px',
                letterSpacing: '0.07em',
                color: 'var(--subtle)',
                border: '1px solid var(--divider)',
                padding: '3px 9px',
                borderRadius: '999px',
              }}
            >
              {chip}
            </span>
          ))}
        </div>
      )}

      {/* Swipe up affordance */}
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          paddingBottom: 'max(env(safe-area-inset-bottom), 1rem)',
          color: 'var(--subtle)',
        }}
      >
        <svg width="20" height="12" viewBox="0 0 20 12" fill="none">
          <path
            d="M2 10L10 2L18 10"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <div
          style={{
            width: '1px',
            height: '20px',
            background: 'var(--subtle)',
            margin: '4px auto 0',
          }}
        />
      </div>
    </Card>
  );
}
