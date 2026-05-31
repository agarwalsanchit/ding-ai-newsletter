import { supabase } from '@/lib/supabase';
import { ApprovedArticle, DailyBrief, Translation, TranslationMap } from '@/lib/types';
import Deck from '@/components/deck/Deck';

export const dynamic = 'force-dynamic';

export default async function HomePage() {
  // "Morning brief" window: today + yesterday (Pacific). DING is a daily
  // curated brief, not a realtime feed — most stories fetched at 8 AM PT were
  // published the previous day, so a today-only filter hid almost everything
  // (article_date is stamped from the story's publish date). A 2-day window
  // surfaces well-curated day-1 news and is resilient to late pipeline runs.
  // Vercel runs in UTC; pipeline stamps article_date in Pacific
  // (TZ=America/Los_Angeles in GH Actions), so we compute dates in that zone.
  const fmtPacific = (d: Date) =>
    new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Los_Angeles' }).format(d); // → "YYYY-MM-DD"
  const windowStart = fmtPacific(new Date(Date.now() - 24 * 60 * 60 * 1000)); // yesterday (PT)

  // Fetch the most recent approved brief in the window (today's if it exists,
  // otherwise yesterday's — so a late/missing run still opens with a brief).
  const { data: briefData } = await supabase
    .from('daily_briefs')
    .select('id, brief_date, editorial_opener, brief_body, transition_line, topic_chips, approved_at')
    .not('approved_at', 'is', null)
    .gte('brief_date', windowStart)
    .order('brief_date', { ascending: false })
    .limit(1);

  const brief = ((briefData?.[0] ?? null) as DailyBrief | null);

  // Fetch approved articles in the window (today + yesterday)
  const { data: approvedData, error: articlesError } = await supabase
    .from('approved_articles')
    .select('*')
    .gte('article_date', windowStart)
    .order('rank_score', { ascending: false })
    .limit(10);

  if (articlesError) {
    console.error('[DING] Failed to fetch approved_articles:', articlesError);
  }

  const approvedArticles = (approvedData ?? []) as ApprovedArticle[];

  // Fetch today's high-confidence pending articles (ai_confidence >= 4 on all axes)
  const { data: pendingData } = await supabase
    .from('articles')
    .select(
      'id, topic, article_date, title, article_brief, balanced_summary, detail_summary, ' +
      'why_it_matters, score_importance, score_urgency, score_interest, source_urls'
    )
    .gte('article_date', windowStart)
    .eq('status', 'pending')
    .gte('ai_confidence_factual', 4)
    .gte('ai_confidence_on_topic', 4)
    .gte('ai_confidence_source', 4)
    .not('title', 'is', null);

  // Exclude articles already promoted to approved_articles
  const approvedArticleIds = new Set(approvedArticles.map((a) => a.article_id));

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const pendingArticles: ApprovedArticle[] = ((pendingData ?? []) as any[])
    .filter((p) => !approvedArticleIds.has(p.id))
    .map((p) => {
      const imp = p.score_importance ?? 3;
      const urg = p.score_urgency   ?? 3;
      const int = p.score_interest  ?? 3;
      return {
        id:               p.id,
        article_id:       p.id,
        topic:            p.topic,
        article_date:     p.article_date,
        title:            p.title,
        article_brief:    p.article_brief   ?? null,
        balanced_summary: p.balanced_summary ?? '',
        detail_summary:   p.detail_summary   ?? null,
        why_it_matters:   p.why_it_matters   ?? '',
        score_importance: imp,
        score_urgency:    urg,
        score_interest:   int,
        rank_score:       imp * 2 + urg + int,
        source_urls:      p.source_urls ?? [],
        approved_at:      '',
        approved_by:      'ai_auto' as const,
        published_at:     null,
        left_perspective:  null,
        right_perspective: null,
      };
    });

  // Merge approved + high-confidence pending, sort by rank_score, cap at 10
  const articles = [...approvedArticles, ...pendingArticles]
    .sort((a, b) => b.rank_score - a.rank_score)
    .slice(0, 10);

  // Translations only exist for approved articles
  let translations: TranslationMap = {};
  if (approvedArticles.length > 0) {
    const { data: translationsData } = await supabase
      .from('translations')
      .select(
        'approved_article_id, language, title_translated, summary_translated, why_it_matters_translated, detail_summary_translated'
      )
      .in('approved_article_id', approvedArticles.map((a) => a.id))
      .eq('language', 'hi');

    if (translationsData) {
      translations = Object.fromEntries(
        (translationsData as Translation[]).map((t) => [t.approved_article_id, t])
      );
    }
  }

  return <Deck brief={brief} articles={articles} translations={translations} />;
}
