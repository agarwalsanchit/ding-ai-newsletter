import { ApprovedArticle } from '@/lib/types';
import Card from './Card';

function formatArticleDate(dateStr: string): string {
  const [year, month, day] = dateStr.split('-').map(Number);
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(
    new Date(year, month - 1, day)
  );
}

function extractDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

function stripEmoji(topic: string): string {
  return topic.split(' ').slice(1).join(' ');
}

export default function ArticleCard({ article }: { article: ApprovedArticle }) {
  return (
    <Card>
      {/* Metadata row */}
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
        {stripEmoji(article.topic)}
        {' · '}
        {formatArticleDate(article.article_date)}
        {article.source_urls[0] && (
          <>{' · '}{extractDomain(article.source_urls[0])}</>
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
          marginBottom: '20px',
        }}
      >
        {article.title}
      </h2>

      {/* Summary — truncated to fit one screen on iPhone 14 (260 chars) */}
      <p
        style={{
          fontFamily: 'var(--font-sans)',
          fontSize: '16px',
          lineHeight: 1.55,
          color: 'var(--text)',
          marginBottom: '20px',
        }}
      >
        {article.balanced_summary.length > 260
          ? article.balanced_summary.slice(0, 260).trimEnd() + '\u2026'
          : article.balanced_summary}
      </p>

      {/* Why it matters */}
      <p
        style={{
          fontFamily: 'var(--font-sans)',
          fontSize: '16px',
          fontStyle: 'italic',
          lineHeight: 1.55,
          color: 'var(--text)',
          marginBottom: '32px',
        }}
      >
        <span>Why it matters:</span>{' '}
        {article.why_it_matters}
      </p>

      {/* Tap to read more — Sitting 6 hook */}
      <p
        style={{
          fontFamily: 'var(--font-sans)',
          fontSize: '13px',
          color: 'var(--subtle)',
        }}
      >
        Tap to read more
      </p>
    </Card>
  );
}
