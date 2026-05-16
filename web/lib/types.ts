export type ApprovedArticle = {
  // Primary key
  id: string;

  // FK to articles — NOT NULL in schema
  article_id: string;

  // NOT NULL columns
  topic: string;
  article_date: string;         // Postgres date → ISO string "YYYY-MM-DD"
  title: string;
  balanced_summary: string;
  why_it_matters: string;

  // Scores 1–5, NOT NULL
  score_importance: number;
  score_urgency: number;
  score_interest: number;

  // GENERATED ALWAYS AS (importance×2 + urgency + interest) STORED
  rank_score: number;

  // NOT NULL DEFAULT '{}'
  source_urls: string[];

  // NOT NULL, timestamptz → ISO string
  approved_at: string;
  approved_by: 'human' | 'ai_auto';

  // Nullable: set when article is published to newsletter / PWA
  published_at: string | null;
};
