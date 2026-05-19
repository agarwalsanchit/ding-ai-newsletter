import { ApprovedArticle, Translation } from '@/lib/types';
import { Language } from '@/lib/hooks/useLanguage';
import Card from './Card';
import LanguageToggle from './LanguageToggle';

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

interface ArticleCardProps {
  article: ApprovedArticle;
  translation: Translation | null;
  lang: Language;
  onToggleLang: () => void;
  onOpenDetail: () => void;
}

export default function ArticleCard({
  article,
  translation,
  lang,
  onToggleLang,
  onOpenDetail,
}: ArticleCardProps) {
  const hasTranslation = !!translation?.title_translated;
  const showHindi = lang === 'hi' && hasTranslation;

  const title   = showHindi ? translation!.title_translated!        : article.title;
  const summary = showHindi ? (translation!.summary_translated ?? article.balanced_summary) : article.balanced_summary;
  const wim     = showHindi ? (translation!.why_it_matters_translated ?? article.why_it_matters) : article.why_it_matters;

  // Phase 3: perspectives indicator
  const hasPerspectives = !!(article.left_perspective && article.right_perspective);

  return (
    <Card>
      {/* Metadata row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '16px',
        }}
      >
        <p
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '11px',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: 'var(--muted)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            flexWrap: 'wrap',
          }}
        >
          <span>{stripEmoji(article.topic)}</span>
          <span>·</span>
          <span>{formatArticleDate(article.article_date)}</span>
          {article.source_urls[0] && (
            <>
              <span>·</span>
              <a
                href={article.source_urls[0]}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                style={{
                  color: 'var(--muted)',
                  textDecoration: 'none',
                  borderBottom: '1px solid var(--divider)',
                }}
              >
                {extractDomain(article.source_urls[0])}
              </a>
            </>
          )}
          {/* Phase 3: perspectives dot */}
          {hasPerspectives && (
            <>
              <span>·</span>
              <span
                style={{ color: 'var(--accent)', fontSize: '9px', letterSpacing: '0.1em' }}
                title="Multiple perspectives available"
              >
                L · R
              </span>
            </>
          )}
        </p>

        {/* Phase 2: language toggle — only if translation exists */}
        {hasTranslation && (
          <LanguageToggle lang={lang} onToggle={onToggleLang} />
        )}
      </div>

      {/* Tappable body */}
      <div
        role="button"
        tabIndex={0}
        onClick={onOpenDetail}
        onKeyDown={(e) => e.key === 'Enter' && onOpenDetail()}
        style={{ cursor: 'pointer' }}
      >
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
          {title}
        </h2>

        <p
          style={{
            fontFamily: 'var(--font-sans)',
            fontSize: '15px',
            lineHeight: 1.5,
            color: 'var(--text)',
            marginBottom: '16px',
            display: '-webkit-box',
            WebkitBoxOrient: 'vertical',
            WebkitLineClamp: 5,
            overflow: 'hidden',
          }}
        >
          {summary}
        </p>

        <p
          style={{
            fontFamily: 'var(--font-sans)',
            fontSize: '15px',
            fontStyle: 'italic',
            lineHeight: 1.5,
            color: 'var(--text)',
          }}
        >
          <span style={{ fontStyle: 'normal', color: 'var(--muted)' }}>
            {showHindi ? 'यह क्यों मायने रखता है: ' : 'Why it matters: '}
          </span>
          {wim}
        </p>
      </div>

      {/* Tap-to-detail affordance */}
      <div
        onClick={onOpenDetail}
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
          cursor: 'pointer',
        }}
      >
        <p
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '10px',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            marginBottom: '6px',
          }}
        >
          {showHindi ? 'अधिक पढ़ें' : 'Tap to read more'}
        </p>
        <svg width="20" height="12" viewBox="0 0 20 12" fill="none">
          <path
            d="M2 2L10 10L18 2"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
    </Card>
  );
}
