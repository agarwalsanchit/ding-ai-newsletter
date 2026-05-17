import { supabase } from '@/lib/supabase';
import { ApprovedArticle } from '@/lib/types';

export const dynamic = 'force-dynamic';

const TOPIC_ORDER = [
  '🚨 Top News',
  '🌍 Geopolitics & World Affairs',
  '💼 Business & Finance',
  '🔬 Science & Technology',
  '🎾 Sports & Entertainment',
  '🏛 Society & Culture',
];

function stripEmoji(topic: string): string {
  // Topics are stored as "🚨 Top News" — drop the first token (emoji) and space
  return topic.split(' ').slice(1).join(' ');
}

function formatArticleDate(dateStr: string): string {
  const [year, month, day] = dateStr.split('-').map(Number);
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(
    new Date(year, month - 1, day)
  );
}

function formatHeaderDate(): string {
  const now = new Date();
  const weekday = now.toLocaleDateString('en-US', { weekday: 'short' }).toUpperCase();
  const month   = now.toLocaleDateString('en-US', { month: 'short' }).toUpperCase();
  const day     = now.getDate();
  return `${weekday}, ${month} ${day}`;
}

function extractDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

export default async function HomePage() {
  let articles: ApprovedArticle[] = [];
  let error = false;

  try {
    const { data, error: queryError } = await supabase
      .from('approved_articles')
      .select('*')
      .not('published_at', 'is', null)
      .order('article_date', { ascending: false })
      .order('rank_score', { ascending: false });

    if (queryError) {
      console.error('[DING] Failed to fetch approved_articles:', queryError);
      error = true;
    } else {
      articles = (data ?? []) as ApprovedArticle[];
    }
  } catch (err) {
    console.error('[DING] Unexpected error:', err);
    error = true;
  }

  // Group by topic
  const grouped = new Map<string, ApprovedArticle[]>();
  for (const article of articles) {
    const list = grouped.get(article.topic) ?? [];
    list.push(article);
    grouped.set(article.topic, list);
  }

  const orderedTopics = TOPIC_ORDER.filter((t) => grouped.has(t));
  for (const t of grouped.keys()) {
    if (!TOPIC_ORDER.includes(t)) orderedTopics.push(t);
  }

  const containerStyle: React.CSSProperties = {
    maxWidth: '720px',
    margin: '0 auto',
    padding: '56px 24px 96px',
  };

  const mutedText: React.CSSProperties = {
    color: 'var(--muted)',
    textAlign: 'center',
    fontSize: '17px',
    lineHeight: 1.6,
  };

  return (
    <div style={{ minHeight: '100vh' }}>
      <div style={containerStyle}>

        {/* ── Header ─────────────────────────────────────────── */}
        <header style={{ marginBottom: '96px' }}>
          <h1
            style={{
              fontFamily: 'var(--font-sans)',
              fontSize: '36px',
              fontWeight: 600,
              letterSpacing: '-0.02em',
              lineHeight: 1,
              marginBottom: '12px',
            }}
          >
            DING News
          </h1>

          <div
            style={{
              display: 'flex',
              alignItems: 'baseline',
              gap: '16px',
              flexWrap: 'wrap',
            }}
          >
            <span
              style={{
                fontFamily: 'var(--font-sans)',
                fontSize: '14px',
                fontWeight: 400,
                color: 'var(--muted)',
              }}
            >
              Signal over noise
            </span>
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '12px',
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
                color: 'var(--subtle)',
              }}
            >
              {formatHeaderDate()}
            </span>
          </div>
        </header>

        {/* ── States ─────────────────────────────────────────── */}
        {error ? (
          <p style={mutedText}>Couldn&apos;t load articles.</p>
        ) : articles.length === 0 ? (
          <p style={mutedText}>Nothing to read yet.</p>
        ) : (
          <main>
            {orderedTopics.map((topic, topicIdx) => {
              const topicArticles = grouped.get(topic)!;
              return (
                <div key={topic}>
                  {/* Divider between sections */}
                  {topicIdx > 0 && (
                    <div style={{ padding: '48px 0' }}>
                      <hr
                        style={{
                          border: 'none',
                          borderTop: '1px solid var(--divider)',
                          margin: 0,
                        }}
                      />
                    </div>
                  )}

                  <section>
                    {/* Section header */}
                    <h2
                      style={{
                        fontFamily: 'var(--font-sans)',
                        fontSize: '24px',
                        fontWeight: 500,
                        letterSpacing: '-0.01em',
                        marginBottom: '24px',
                      }}
                    >
                      {stripEmoji(topic)}
                    </h2>

                    {/* Articles */}
                    {topicArticles.map((article, idx) => (
                      <div
                        key={article.id}
                        style={{ marginTop: idx > 0 ? '64px' : 0 }}
                      >
                        {/* 1. Metadata row */}
                        <p
                          style={{
                            fontSize: '13px',
                            color: 'var(--muted)',
                            marginBottom: '12px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                          }}
                        >
                          <span style={{ fontFamily: 'var(--font-sans)' }}>
                            {formatArticleDate(article.article_date)}
                          </span>
                          {article.source_urls[0] && (
                            <>
                              <span style={{ color: 'var(--subtle)' }}>·</span>
                              <span style={{ fontFamily: 'var(--font-mono)' }}>
                                {extractDomain(article.source_urls[0])}
                              </span>
                            </>
                          )}
                        </p>

                        {/* 2. Headline */}
                        <h3
                          style={{
                            fontFamily: 'var(--font-sans)',
                            fontSize: 'clamp(26px, 5vw, 32px)',
                            fontWeight: 600,
                            lineHeight: 1.15,
                            letterSpacing: '-0.02em',
                            marginBottom: '20px',
                          }}
                        >
                          {article.title}
                        </h3>

                        {/* 3. Summary */}
                        <p
                          style={{
                            fontFamily: 'var(--font-sans)',
                            fontSize: '17px',
                            fontWeight: 400,
                            lineHeight: 1.6,
                            color: 'var(--text)',
                          }}
                        >
                          {article.balanced_summary}
                        </p>

                        {/* 4. Why it matters */}
                        <p
                          style={{
                            fontFamily: 'var(--font-sans)',
                            fontSize: '17px',
                            fontStyle: 'italic',
                            lineHeight: 1.6,
                            color: 'var(--text)',
                            marginTop: '24px',
                          }}
                        >
                          <span style={{ fontWeight: 600, color: 'var(--muted)' }}>Why it matters</span>:{' '}
                          {article.why_it_matters}
                        </p>
                      </div>
                    ))}
                  </section>
                </div>
              );
            })}
          </main>
        )}
      </div>
    </div>
  );
}
