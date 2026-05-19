-- =============================================================================
-- Pipeline additions — DESIGN.md tasks 2.4–2.7b
-- =============================================================================

-- Add detail_summary to articles table (pipeline generates it alongside balanced_summary)
ALTER TABLE articles ADD COLUMN IF NOT EXISTS detail_summary text;

-- Expand processing_log call_type check to include brief_generator
ALTER TABLE processing_log DROP CONSTRAINT IF EXISTS processing_log_call_type_check;
ALTER TABLE processing_log ADD CONSTRAINT processing_log_call_type_check
    CHECK (call_type IN (
        'article_processor',
        'brief_generator',
        'translation_hi',
        'translation_mr',
        'newsletter'
    ));
