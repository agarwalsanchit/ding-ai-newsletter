import { supabase } from '@/lib/supabase';
import { ApprovedArticle, DailyBrief } from '@/lib/types';
import Deck from '@/components/deck/Deck';

export const dynamic = 'force-dynamic';

export default async function HomePage() {
  const today = new Date().toISOString().split('T')[0];

  // Fetch today's brief (null if not yet generated)
  const { data: briefData } = await supabase
    .from('daily_briefs')
    .select('id, brief_date, editorial_opener, brief_body, transition_line, topic_chips, approved_at')
    .eq('brief_date', today)
    .not('approved_at', 'is', null)
    .maybeSingle();

  const brief = briefData as DailyBrief | null;

  // Fetch top 10 published articles by rank_score
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

  return <Deck brief={brief} articles={articles} />;
}
