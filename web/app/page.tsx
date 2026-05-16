import { supabase } from '@/lib/supabase';
import { ApprovedArticle } from '@/lib/types';

function formatDate(dateStr: string): string {
  const [year, month, day] = dateStr.split('-').map(Number);
  return new Date(year, month - 1, day).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
}

function extractDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

export default async function Home() {
  let articles: ApprovedArticle[] = [];
  let error = false;

  try {
    const { data, error: queryError } = await supabase
      .from('approved_articles')
      .select('*')
      .order('rank_score', { ascending: false })
      .order('published_at', { ascending: false });

    if (queryError) {
      console.error('[DING] Failed to fetch approved_articles:', queryError);
      error = true;
    } else {
      articles = (data ?? []) as ApprovedArticle[];
    }
  } catch (err) {
    console.error('[DING] Unexpected error fetching articles:', err);
    error = true;
  }

  return (
    <div className="min-h-screen bg-white dark:bg-zinc-950">
      <div className="mx-auto max-w-[640px] px-4 py-8">
        <h1 className="mb-8 text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50">
          DING News
        </h1>

        {error ? (
          <p className="text-center text-zinc-500 dark:text-zinc-400">
            Could not load articles
          </p>
        ) : articles.length === 0 ? (
          <p className="text-center text-zinc-500 dark:text-zinc-400">
            No articles yet
          </p>
        ) : (
          <ul className="flex flex-col gap-4">
            {articles.map((article) => (
              <li
                key={article.id}
                className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
              >
                <div className="mb-2 flex items-center gap-2">
                  <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
                    {article.topic}
                  </span>
                  <span className="text-xs text-zinc-400 dark:text-zinc-600">·</span>
                  <span className="text-xs text-zinc-500 dark:text-zinc-400">
                    {formatDate(article.article_date)}
                  </span>
                  {article.source_urls[0] && (
                    <>
                      <span className="text-xs text-zinc-400 dark:text-zinc-600">·</span>
                      <span className="text-xs text-zinc-500 dark:text-zinc-400">
                        {extractDomain(article.source_urls[0])}
                      </span>
                    </>
                  )}
                </div>

                <h2 className="mb-2 text-base font-bold leading-snug text-zinc-900 dark:text-zinc-50">
                  {article.title}
                </h2>

                <p className="text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
                  {article.balanced_summary.length > 150
                    ? article.balanced_summary.slice(0, 150) + '…'
                    : article.balanced_summary}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
