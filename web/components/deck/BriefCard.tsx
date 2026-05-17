import { DailyBrief } from '@/lib/types';
import Card from './Card';

function formatBriefDate(dateStr: string): string {
  const [year, month, day] = dateStr.split('-').map(Number);
  const d = new Date(year, month - 1, day);
  const weekday = d.toLocaleDateString('en-US', { weekday: 'long' }).toUpperCase();
  const monthName = d.toLocaleDateString('en-US', { month: 'long' }).toUpperCase();
  return `${weekday}, ${monthName} ${day}`;
}

export default function BriefCard({ brief }: { brief: DailyBrief | null }) {
  const dateLabel = brief
    ? formatBriefDate(brief.brief_date)
    : new Date().toLocaleDateString('en-US', {
        weekday: 'long',
        month: 'long',
        day: 'numeric',
      }).toUpperCase();

  return (
    <Card>
      {/* Date */}
      <p
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '11px',
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          color: 'var(--subtle)',
          marginBottom: '24px',
        }}
      >
        {dateLabel}
      </p>

      {/* Editorial opener */}
      <h1
        style={{
          fontFamily: 'var(--font-sans)',
          fontSize: '32px',
          fontWeight: 600,
          lineHeight: 1.1,
          letterSpacing: '-0.02em',
          marginBottom: '20px',
        }}
      >
        {brief ? brief.editorial_opener : 'Good morning.'}
      </h1>

      {/* Brief body */}
      <p
        style={{
          fontFamily: 'var(--font-sans)',
          fontSize: '17px',
          lineHeight: 1.55,
          marginBottom: '20px',
        }}
      >
        {brief ? brief.brief_body : "Today\u2019s deck is loading\u2026"}
      </p>

      {/* Transition line */}
      <p
        style={{
          fontFamily: 'var(--font-sans)',
          fontSize: '15px',
          lineHeight: 1.55,
          color: 'var(--muted)',
          marginBottom: '32px',
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
            gap: '8px',
            marginBottom: '0',
          }}
        >
          {brief.topic_chips.map((chip) => (
            <span
              key={chip}
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '10px',
                letterSpacing: '0.08em',
                color: 'var(--muted)',
                border: '1px solid var(--divider)',
                padding: '4px 10px',
                borderRadius: '999px',
              }}
            >
              {chip}
            </span>
          ))}
        </div>
      )}

      {/* Swipe up affordance — absolute at bottom, safe-area aware */}
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
        <svg
          width="20"
          height="12"
          viewBox="0 0 20 12"
          fill="none"
        >
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
