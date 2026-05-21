-- Lower the auto_approved confidence threshold from == 5 to >= 4.
-- The original 5/5/5 constraint was too strict: sports articles reliably
-- score factual confidence of 4 (Claude can't self-verify match results),
-- and many accurate articles score 4 on one axis. Confidence >= 4 on all
-- three axes is a reliable quality signal across all topics.
ALTER TABLE articles DROP CONSTRAINT IF EXISTS articles_check1;

ALTER TABLE articles ADD CONSTRAINT articles_check1 CHECK (
    status != 'auto_approved' OR (
        ai_confidence_factual  >= 4 AND
        ai_confidence_on_topic >= 4 AND
        ai_confidence_source   >= 4
    )
);
