export type ApprovedArticle = {
  id: string;
  article_id: string;
  topic: string;
  article_date: string;
  title: string;
  balanced_summary: string;
  why_it_matters: string;
  score_importance: number;
  score_urgency: number;
  score_interest: number;
  rank_score: number;
  source_urls: string[];
  approved_at: string;
  approved_by: 'human' | 'ai_auto';
  published_at: string | null;
  detail_summary: string | null;
  // Phase 3 — perspectives (null until backend generates them)
  left_perspective: string | null;
  right_perspective: string | null;
};

export type DailyBrief = {
  id: string;
  brief_date: string;
  editorial_opener: string;
  brief_body: string;
  transition_line: string;
  topic_chips: string[];
  approved_at: string | null;
};

// Phase 2 — translation row for a single article in one language
export type Translation = {
  approved_article_id: string;
  language: 'hi' | 'mr';
  title_translated: string | null;
  summary_translated: string | null;
  why_it_matters_translated: string | null;
  detail_summary_translated: string | null;
};

// Keyed by approved_article_id for O(1) lookup in the deck
export type TranslationMap = Record<string, Translation>;
