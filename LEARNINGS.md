# DING.AI — Core Learnings & Competitive Differentiation

> Updated May 21, 2026 (Phase 2 frontend shipped; PWA live on Vercel).
> These are the non-obvious lessons learned building a production AI news pipeline from scratch.

---

## 1. The Filtering Problem Is Harder Than the Generation Problem

Every AI news pipeline generates plausible-sounding summaries. The real engineering problem is **deciding what not to show**. We ran into every flavor of this:

**Overfiltering:** A 7-day URL dedup window accumulated 89 URLs during development (multiple test runs), silently blocking most of the day's news. Real stories about Iran peace talks, the Elon/OpenAI trial verdict, and Russia nuclear drills were all filtered. The fix was a 2-day window, which in production (one run/day) stays under ~20 URLs.

**Underfiltering via semantic drift:** Keyword-specific Tavily queries ("OpenAI Anthropic Google DeepMind xAI") produced great results on days when those companies had news, but were arbitrary — they anchored on the query, not on what was actually newsworthy. Reverted to generic topic queries. The pipeline should follow the news, not hunt for specific players.

**False positives in duplicate detection:** Claude's duplicate detection was only as good as its reference data. When the reference was a JSON history file that only updated on newsletter send, test runs had stale (or empty) context and Claude marked real new stories as duplicates. Fix: pull the recent-coverage context from `approved_articles` (what was actually approved) rather than the JSON file (what was sent).

**Lesson:** The hardest part of news curation is not "generate a summary" but "is this actually new information for this reader today?" That question requires authoritative state — a database, not a file.

---

## 2. Content Quality Is a Function of Source Quality

The best AI summary of a boxscore page is still a boxscore. Tavily sports results were predominantly ESPN watch pages, CBS Sports video clips, and Fox Sports live score trackers — all with zero article text. Claude would either hallucinate sports context or produce a summary of the URL slug.

Fix: `site:apnews.com OR site:reuters.com OR site:bbc.com OR site:espn.com/story` in the sports query forces wire-service editorial articles. A 13-pattern URL blocklist catches video/boxscore/podcast pages across all sections.

**Lesson:** Prompt engineering on the AI processing side gives you maybe 10% improvement. Source query engineering on the fetch side gives you 80%. A great model processing bad inputs is still bad output.

---

## 3. "Followup" vs "Duplicate" Is the Most Important Prompt Engineering Decision

Claude's default behavior when asked to detect duplicates was to call many things "followup" — it was hedging, avoiding the false negative. But from a reader's perspective, the failure mode is the opposite: seeing the same Iran peace talks story two days in a row with no new information is worse than missing a marginal update.

The prompt now says: **when uncertain between followup and duplicate, choose duplicate.** And "followup" requires a materially new fact — a number changed, a decision made, a new actor, an outcome announced. More reporting on the same situation is duplicate.

This single prompt change dramatically reduced repetitive content in the daily deck.

---

## 4. Top News Should Be Computed, Not Fetched

Early design: a dedicated "Top News" Tavily query restricted to `reuters.com apnews.com bbc.com`. This reliably returned the most prominent international wire stories but had a structural flaw: on any given day, the most interesting story might be in Tech or Business, not in "breaking news" wire services. And the dedicated query frequently returned video bulletins and homepage aggregator pages.

Current design: `flag_top_news()` runs after all 5 sections are processed and picks the article with the highest `score_importance + score_urgency` across everything. The article keeps its original section's content but gets relabeled "🚨 Top News" in the deck.

**Lesson:** For "what's the top story today" — let the AI score everything and compute the answer, don't try to fetch it from a dedicated query. The score is more reliable than the query.

---

## 5. Draft Mode Must Be Idempotent

Early in development, each draft run stamped `published_at` on approved articles. Running the newsletter in draft mode 3 times in one afternoon consumed all approved articles — subsequent draft runs found zero articles (the query filters `WHERE published_at IS NULL`) and fell back to the legacy Tavily-based path, producing completely different output.

Fix: `published_at` is only stamped when `send_mode="send"`. Draft runs are now safe to run repeatedly without side effects.

**Lesson:** Any pipeline that modifies state as a side effect of observation is undebuggable. Operations that look like reads (generate draft email) should not write production state.

---

## 6. Human Review Is a Teaching System, Not a Blocking Gate

The safety gate produces a row in `human_reviews` for every approved and rejected article: which checks passed, which failed, who reviewed it. The calibration mode records when the human score differs from the AI score, and why.

Over time this becomes a dataset: what kinds of articles do humans approve vs. reject? Where does the AI's confidence not match the human's? What topics get consistently low urgency scores despite high importance?

This data can close the loop — fine-tuning or prompt updates based on calibration disagreements. We haven't done that yet, but the infrastructure exists from day one.

**Lesson:** Build the feedback loop before you need it. A gate without a feedback loop is just latency.

---

## 7. Score-Based Demotion Is Better Than Score-Based Rejection

Early approach: reject articles below a score threshold before they reach the newsletter. Problem: this meant good articles that happened to have low scores (e.g., a genuinely interesting niche story scored low by the AI) disappeared entirely.

Current approach: articles with `score_importance < 2 OR score_interest < 2` are **demoted** to Quick Hits, not dropped. They appear as one-sentence bullets if the AI finds them interesting enough, but they don't get a full section write-up. The deck still benefits from their signal; readers aren't burdened by a full article.

**Lesson:** Tiered presentation (full article vs. quick hit) is almost always better than binary include/exclude. Design for graceful degradation, not hard cutoffs.

---

## 8. max_tokens Is a Feature, Not a Limit

The first time the pipeline processed a Top News article (with `detail_summary` + `balanced_summary` + all scores in a single JSON output), it silently truncated mid-JSON: `Unterminated string starting at: line 104 column 23`. The article was real — Russia nuclear drills — and Claude had real things to say about it. But `max_tokens=4096` wasn't enough for a full batch response.

Fix: `max_tokens=8192`. No more truncation.

**Lesson:** Set `max_tokens` based on what you actually need, not as a cost-cutting measure. A truncated response costs the same as a complete one but produces a parsing error.

---

## What Differentiates DING.AI from Other AI News Platforms

Most "AI news" products are one of:
1. An LLM prompted to summarize today's news (no persistent state, no dedup, no human in the loop)
2. An RSS aggregator with AI-written summaries (no curation signal, no quality filtering)
3. A personalization engine (tells you what you want to hear, not what's important)

DING.AI is different in three ways:

### Human + AI, Not AI Alone

Every article that appears in the deck has been reviewed by a human (or auto-approved at a very high AI confidence threshold — 5/5/5 on all three confidence axes). The human gate is not a bottleneck; it's a teacher. The review CLI is designed to take under 10 minutes per day and produces calibration data that can improve the AI's scoring over time.

This is not a safety theater checkbox. The five gate questions (factually accurate? on-topic? source credible? not duplicate? safe to publish?) map directly to the failure modes we observed in the first weeks of running the pipeline. Each question has a real counterexample from production.

### Signal Over Noise as an Architectural Constraint

The deck is closed-ended by design. There are 7–10 articles. That's it. No "load more." No related articles. No engagement hooks. The product is designed for a 10-minute morning ritual, and every architectural decision is evaluated against that constraint.

This is unusual. Most AI news products compete on coverage breadth ("we cover 10,000 sources"). DING.AI competes on curation depth: we'd rather miss a story than overwhelm the reader. The closed deck is the product.

### The Pipeline Is a Learnable System

Every decision the AI makes is logged: what it scored, what it classified as duplicate, what confidence it assigned. Every decision the human makes is logged: what they approved, what they rejected, where they disagreed with the AI's scores. The processing_log tracks every API call with token counts and cost.

This means the pipeline can be debugged, tuned, and eventually improved by its own output data. Other AI news products treat the model as a black box. We treat the model as a collaborator whose judgments can be verified, overridden, and taught.

---

---

## 9. RLS Blocks the Anon Key — Always Test Access Separately From the Service Role

The `articles` table has Row Level Security enabled in Supabase. The pipeline uses the service-role key, which bypasses RLS. The PWA uses the anon key, which is subject to RLS. These look identical in code — both use the Supabase JS client — but return completely different data.

When we tried to surface high-confidence pending articles in the PWA, the query returned `[]`. The pipeline had written articles to the DB; they existed. But the anon key had no SELECT policy on `articles`, so Supabase silently returned an empty array rather than an error.

Fix: add a Supabase RLS policy (`CREATE POLICY "anon_read_high_confidence_pending" ON articles FOR SELECT TO anon USING (...)`) and save it as a migration so it's reproducible.

**Lesson:** Whenever you add a new table query to the frontend, test it explicitly with the anon key (or Supabase's "Row Level Security" tab in the dashboard) before deploying. Do not assume the service-role-based pipeline tests cover the frontend access path.

---

## 10. GitHub Actions Cron Is Not Reliable for Time-Sensitive Runs

The scheduled workflow (`0 15 * * *` = 8 AM PDT) sometimes doesn't fire at the scheduled time. On GitHub's free/hobby tier, cron jobs can be delayed by 30 minutes to several hours, especially during periods of high load or platform issues.

For a daily news product, a delayed pipeline means an empty deck at the start of users' morning routine — exactly when they're most likely to open the app.

**Lesson:** Build manual trigger capability into every time-sensitive workflow (`workflow_dispatch` input). Treat the cron as a default, not a guarantee. If the product needs the pipeline to have run by 9 AM, either accept occasional empty states (current approach) or add a monitoring check that alerts when the pipeline hasn't run by a specific time.

---

## 11. flag_top_news() Corrupts Unprocessed Articles — A Data Integrity Bug

`flag_top_news()` runs after every pipeline execution and picks the highest `score_importance + score_urgency` article from the day's approved + pending pool, then relabels its `topic` field to "🚨 Top News" in both the `articles` and `approved_articles` tables.

The bug: if the pipeline ran partially (e.g., only 3 of 5 sections processed), `flag_top_news()` may relabel an article from a section that wasn't processed in the current run. That article still has `status=pending` but now has `topic="🚨 Top News"` — which no longer matches any Tavily section key. In subsequent pipeline runs, the idempotency check finds the article already has `processed_at` set (or not, depending on when it was flagged), but either way the article won't be correctly reprocessed.

Effect observed on May 21: two articles appeared with topic "🚨 Top News" while unprocessed, blocking them from being picked up by any subsequent Claude call.

**Lesson:** Any function that modifies shared state (article topics) based on computed rankings must be bounded: only flag articles that were successfully processed in the current run, not all pending articles for the day. Better yet, make Top News a derived flag (a computed column or a query-time decoration) rather than a stored topic mutation.

---

## 12. Confidence Threshold ≥ 4 Is Too Strict for Factual Sports Content

The RLS policy and Quick Hits pool both use `ai_confidence_factual >= 4` as a gate. Sports match results — factually simple, verifiable events — reliably score `ai_confidence_factual = 2` from Claude. Claude marks low factual confidence because it cannot verify box scores against external sources in its context.

Effect: a La Liga match article that was accurately summarized was blocked from appearing in the PWA deck due to a factual confidence score of 2, despite having `ai_confidence_on_topic = 5` and `ai_confidence_source = 5`.

**Lesson:** The confidence threshold was designed for general news (geopolitics, finance) where factual errors are hard to detect and high-stakes. Sports results are a special case: they're factually simple but structurally hard for Claude to self-verify. Options: (a) lower the global factual threshold to ≥ 3; (b) apply topic-aware thresholds (sports: factual ≥ 2); (c) accept that sports articles will sometimes be blocked by the threshold. This tradeoff hasn't been resolved.

---

## 13. Today-Only Date Requires Matching Timezones Across Pipeline and Frontend

The pipeline stamps `article_date` using Python's `date.today()` which resolves to Pacific time in GitHub Actions (`TZ: America/Los_Angeles`). The PWA computes "today" in Next.js server components running on Vercel, where the server runs in UTC.

If the PWA uses `new Date().toISOString().slice(0, 10)` for "today," it will be a UTC date. An article fetched at 11 PM Pacific on May 20 is stamped `article_date = 2026-05-20`, but the UTC date at that moment is `2026-05-21`. The PWA would show that article under May 21, or miss it entirely if querying for May 20.

Fix: `Intl.DateTimeFormat('en-CA', { timeZone: 'America/Los_Angeles' }).format(new Date())` in `page.tsx` — explicitly formats today's date in Pacific time, matching the pipeline's timezone assumption.

**Lesson:** Any system where two components compute "today" independently must agree on timezone. Document the timezone convention at the schema level, not just in code comments.

---

## What to Watch For

- **Sports content quality varies by time of day.** Wire service articles about matches take a few hours to appear in Tavily's index. If the pipeline runs immediately after a match ends, only boxscores may be available. Running at 8 AM Pacific catches the prior evening's results from European and Asian sports.

- **Dedup context grows stale after extended breaks.** If the pipeline hasn't run for 3+ days, the `approved_articles` context window (7 days) may not cover the gap fully. The JSON history file provides a fallback but is less reliable.

- **Auto-approval rate will drift.** As the pipeline processes more days, Claude may adapt its confidence calibration. Periodically check what fraction of articles are auto-approved vs. pending — if the auto-approval rate climbs above 50%, the confidence threshold may need tightening.

- **Confidence threshold calibration needed for sports.** See Learning 12. `ai_confidence_factual >= 4` consistently blocks accurate sports articles. Revisit before the next major pipeline change.

- **flag_top_news() bug still unresolved.** See Learning 11. Partial pipeline runs leave "🚨 Top News" labels on unprocessed articles. Until fixed, manually check `articles` for topic="🚨 Top News" after any partial pipeline run.
