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

  // Fetch top 10 approved articles by rank_score
  const { data: articlesData, error: articlesError } = await supabase
    .from('approved_articles')
    .select('*')
    .not('published_at', 'is', null)
    .order('rank_score', { ascending: false })
    .limit(10);

  if (articlesError) {
    console.error('[DING] Failed to fetch approved_articles:', articlesError);
  }

  const articles = (articlesData ?? []) as ApprovedArticle[];

  // Phase 2: fetch Hindi translations for the articles we're showing
  let translations: TranslationMap = {};
  if (articles.length > 0) {
    const { data: translationsData } = await supabase
      .from('translations')
      .select(
        'approved_article_id, language, title_translated, summary_translated, why_it_matters_translated, detail_summary_translated'
      )
      .in('approved_article_id', articles.map((a) => a.id))
      .eq('language', 'hi');

    if (translationsData) {
      translations = Object.fromEntries(
        (translationsData as Translation[]).map((t) => [t.approved_article_id, t])
      );
    }
  }

  return <Deck brief={brief} articles={articles} translations={translations} />;
}
