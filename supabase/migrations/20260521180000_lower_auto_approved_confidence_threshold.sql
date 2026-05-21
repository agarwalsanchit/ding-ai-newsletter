-- Lower the auto_approved confidence threshold from == 5 to >= 3.
-- Original 5/5/5 was too strict. >= 4 still too few articles in practice
-- (sports factual scores, niche topics). >= 3 is the floor — below this,
-- Claude is signalling genuine doubt about facts, topic fit, or source.
-- The deck caps at 10 by rank_score so low-scoring articles sort to the back.
ALTER TABLE articles DROP CONSTRAINT IF EXISTS articles_check1;

ALTER TABLE articles ADD CONSTRAINT articles_check1 CHECK (
    status != 'auto_approved' OR (
        ai_confidence_factual  >= 3 AND
        ai_confidence_on_topic >= 3 AND
        ai_confidence_source   >= 3
    )
);
