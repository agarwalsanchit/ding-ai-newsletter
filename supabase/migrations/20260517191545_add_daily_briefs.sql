CREATE TABLE daily_briefs (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brief_date        date NOT NULL UNIQUE,
    editorial_opener  text NOT NULL,
    brief_body        text NOT NULL,
    transition_line   text NOT NULL,
    topic_chips       text[] NOT NULL DEFAULT '{}',
    generated_at      timestamptz NOT NULL DEFAULT now(),
    approved_at       timestamptz,
    approved_by       text CHECK (approved_by IN ('human', 'ai_auto')),
    ai_confidence     smallint CHECK (ai_confidence BETWEEN 1 AND 5)
);

-- RLS for the new table
ALTER TABLE daily_briefs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public can read approved briefs"
    ON daily_briefs FOR SELECT TO anon
    USING (approved_at IS NOT NULL);
