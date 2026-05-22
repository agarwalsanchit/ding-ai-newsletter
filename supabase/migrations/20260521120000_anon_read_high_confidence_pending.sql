-- Allow the public (anon) Supabase client to read high-confidence pending
-- articles so the PWA can surface fresh content without waiting for human review.
-- Only articles where all three ai_confidence axes >= 4 are exposed.
CREATE POLICY "anon_read_high_confidence_pending"
ON articles
FOR SELECT TO anon
USING (
  status = 'pending'
  AND ai_confidence_factual  >= 4
  AND ai_confidence_on_topic >= 4
  AND ai_confidence_source   >= 4
  AND title IS NOT NULL
);
