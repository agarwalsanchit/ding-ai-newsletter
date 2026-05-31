import { supabase } from '@/lib/supabase';
import { ApprovedArticle, DailyBrief, Translation, TranslationMap } from '@/lib/types';
import Deck from '@/components/deck/Deck';

export const dynamic = 'force-dynamic';

export default async function HomePage() {
  // Always show today's content only. Vercel runs in UTC; pipeline stamps
  // article_date from Pacific time (TZ=America/Los_Angeles in GH Actions).
  // Use the pipeline's timezone so dates align.
  const today = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Los_Angeles',
  }).format(new Date()); // → "YYYY-MM-DD"

  // Fetch today's approved brief (null if not yet generated/approved)
  const { data: briefData } = await supabase
    .from('daily_briefs')
    .select('id, brief_date, editorial_opener, brief_body, transition_line, topic_chips, approved_at')
    .not('approved_at', 'is', null)
    .eq('brief_date', today)
    .maybeSingle();

  const brief = briefData as DailyBrief | null;

  // Fetch today's approved articles
  const { data: approvedData, error: articlesError } = await supabase
    .from('approved_articles')
    .select('*')
    .eq('article_date', today)
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
    .eq('article_date', today)
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
