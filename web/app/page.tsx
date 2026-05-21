import { supabase } from '@/lib/supabase';
import { ApprovedArticle, DailyBrief, Translation, TranslationMap } from '@/lib/types';
import Deck from '@/components/deck/Deck';

export const dynamic = 'force-dynamic';

export default async function HomePage() {
  // Fetch most recently approved brief (fallback to last generated if today's isn't ready)
  const { data: briefData } = await supabase
    .from('daily_briefs')
    .select('id, brief_date, editorial_opener, brief_body, transition_line, topic_chips, approved_at')
    .not('approved_at', 'is', null)
    .order('brief_date', { ascending: false })
    .limit(1)
    .maybeSingle();

  const brief = briefData as DailyBrief | null;

  // Most recent date with approved articles
  const { data: latestApproved } = await supabase
    .from('approved_articles')
    .select('article_date')
    .order('article_date', { ascending: false })
    .limit(1)
    .maybeSingle();

  // Most recent date with high-confidence pending articles (ai_confidence >= 4 on all axes)
  const { data: latestPending } = await supabase
    .from('articles')
    .select('article_date')
    .eq('status', 'pending')
    .gte('ai_confidence_factual', 4)
    .gte('ai_confidence_on_topic', 4)
    .gte('ai_confidence_source', 4)
    .not('title', 'is', null)
    .order('article_date', { ascending: false })
    .limit(1)
    .maybeSingle();

  // Use whichever date is more recent
  const approvedDate = latestApproved?.article_date ?? '';
  const pendingDate  = latestPending?.article_date  ?? '';
  const deckDate = (pendingDate > approvedDate ? pendingDate : approvedDate)
    || new Date().toISOString().slice(0, 10);

  // Fetch approved articles for deckDate
  const { data: approvedData, error: articlesError } = await supabase
    .from('approved_articles')
    .select('*')
    .eq('article_date', deckDate)
    .order('rank_score', { ascending: false })
    .limit(10);

  if (articlesError) {
    console.error('[DING] Failed to fetch approved_articles:', articlesError);
  }

  const approvedArticles = (approvedData ?? []) as ApprovedArticle[];

  // Fetch high-confidence pending articles for deckDate
  const { data: pendingData } = await supabase
    .from('articles')
    .select(
      'id, topic, article_date, title, article_brief, balanced_summary, detail_summary, ' +
      'why_it_matters, score_importance, score_urgency, score_interest, source_urls'
    )
    .eq('article_date', deckDate)
    .eq('status', 'pending')
    .gte('ai_confidence_factual', 4)
    .gte('ai_confidence_on_topic', 4)
    .gte('ai_confidence_source', 4)
    .not('title', 'is', null);

  // Exclude articles already in approved_articles (approved after pipeline ran)
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
