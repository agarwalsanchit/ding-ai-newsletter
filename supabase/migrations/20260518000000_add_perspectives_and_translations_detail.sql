-- Phase 3: left/right perspectives per approved article (nullable until backend generates them)
ALTER TABLE approved_articles
  ADD COLUMN IF NOT EXISTS left_perspective  text,
  ADD COLUMN IF NOT EXISTS right_perspective text;

-- Phase 2: detail_summary_translated for the detail view in translated language
ALTER TABLE translations
  ADD COLUMN IF NOT EXISTS detail_summary_translated text;
