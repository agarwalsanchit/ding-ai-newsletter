# DING.AI — Architecture

> Last updated: May 19, 2026
> Reflects the two-script pipeline introduced in Phase 2 (pipeline.py + newsletter.py).

---

## Overview

DING.AI is a daily AI news product with two delivery surfaces:

1. **Email newsletter** — HTML email sent via Brevo to subscribers
2. **PWA card deck** — swipeable mobile web app served from Vercel

Both surfaces read from the same **Supabase database**, which is the authoritative store of all article content. Nothing of importance lives in flat files.

---

## Two-Script Architecture

The pipeline is split into two scripts that run sequentially in GitHub Actions:

```
pipeline.py      →    newsletter.py
(fetch + process)     (render + send)
```

This split was intentional:
- `pipeline.py` does the expensive, slow work: 5 Tavily queries + 5+ Claude calls + DB writes
- `newsletter.py` reads from the DB result; if the DB has enough approved articles it's just a layout call
- The split enables human review between pipeline and send (review_cli.py runs in between on local machine)

---

## Data Flow

```
                        ┌─────────────────────────────────────┐
                        │          pipeline.py (daily)         │
                        │                                       │
  Tavily API ──────────▶│  1. Build recent-coverage context    │
  (5 queries)           │     from approved_articles (7 days)  │
                        │  2. Fetch 5 sections × up to 10      │
                        │     articles                          │
                        │  3. persist_fetched_articles()        │
                        │     → articles table (status=pending) │
                        │  4. Idempotency check                 │
                        │  5. process_topic() × 5              │
  Claude (claude-       │     → 1 Claude call per section      │
  sonnet-4-6) ─────────▶│     → updates articles table         │
                        │     → inserts approved_articles if   │
                        │       all-5 confidence               │
                        │  6. flag_top_news()                   │
                        │     → picks highest I+U article       │
                        │  7. generate_brief()                  │
                        │     → inserts daily_briefs            │
                        └──────────────┬──────────────────────┘
                                       │
                                       ▼ (human review optional)
                                 review_cli.py
                                 → safety gate (5 questions)
                                 → calibration (score override)
                                 → brief review
                                       │
                                       ▼
                        ┌─────────────────────────────────────┐
                        │         newsletter.py (daily)        │
                        │                                       │
                        │  1. Read approved_articles (today)   │
                        │  2. Split: full-section vs. demoted  │
                        │  3. Fetch high-confidence pending    │
                        │     for Quick Hits pool              │
                        │  4. Read approved daily_brief        │
                        │  5. Claude layout call               │
                        │     → HTML email                     │
                        │  6. Send via Brevo (if send mode)    │
                        │  7. Stamp published_at (send only)   │
                        │  8. Archive to docs/issues/          │
                        └─────────────────────────────────────┘
                                       │
                               ┌───────┴───────┐
                               ▼               ▼
                          Brevo email      Vercel PWA
                          (subscribers)   (approved_articles
                                           + daily_briefs)
```

---

## News Fetching

Five Tavily queries per day (`search_depth="advanced"`, `days=2`, `topic="news"`, `max_results=10`):

| Section | Query strategy |
|---|---|
| 🌍 Geopolitics & World Affairs | Generic topic terms |
| 💼 Business & Finance | Generic topic terms |
| 🔬 Science & Technology | Generic topic terms including AI/ML focus |
| 🎾 Sports & Entertainment | Wire-service restricted: `site:apnews.com OR site:reuters.com OR site:bbc.com OR site:espn.com/story` to avoid boxscores/video pages |
| 🏛 Society & Culture | Generic topic terms |

Top News is **not a Tavily query** — it is a computed flag (`flag_top_news()`) applied post-processing to the article with the highest `score_importance + score_urgency` across all sections.

### URL Blocklist

Before inserting into Supabase, each URL is checked against 13 patterns that indicate non-article pages (video embeds, boxscores, live-score trackers, podcast pages, photo galleries). These pages return zero summarisable text and would cause Claude to produce hallucinated or empty summaries.

### Dedup Window

URL-exact dedup against articles fetched in the **last 2 days** (keyed on `fetched_at`, not `article_date`). Two-day window is intentional: a 7-day window accumulated too many URLs during development and blocked real news. In production (one run/day), the dedup set stays under ~20 URLs.

---

## Article Lifecycle

```
fetched_at set, status=pending
         │
         ▼ (pipeline.py process_topic)
   ┌─────────────────────────────────────┐
   │ Claude assigns:                      │
   │  relationship_to_recent:            │
   │    "duplicate"  → auto_rejected     │
   │    "new"|"followup":                │
   │      all confidence==5 → auto_approved │
   │      any confidence<5  → pending    │
   └─────────────────────────────────────┘
         │
         ├─── auto_approved → copied to approved_articles (approved_by='ai_auto')
         ├─── auto_rejected → stays in articles table, excluded from review
         └─── pending → surfaces in review_cli.py safety gate
                           │
                           ├─── approved → copied to approved_articles (approved_by='human')
                           └─── rejected → stays in articles table
```

Secondary articles (merged into a primary by Claude) are marked `auto_rejected` without setting `processed_at`, which satisfies the DB check constraint while keeping them out of the review queue.

---

## Claude Usage

| Call | Script | Model | max_tokens | Purpose |
|---|---|---|---|---|
| article_processor | pipeline.py | claude-sonnet-4-6 | 8192 | Per-topic batch: titles, summaries, scores, relationship |
| brief_generator | pipeline.py | claude-sonnet-4-6 | 1024 | Daily brief card text |
| approved_newsletter | newsletter.py | claude-sonnet-4-6 | 8096 | Layout-only: formats pre-written content into HTML |
| fallback_newsletter | newsletter.py | claude-sonnet-4-6 | 8096 | Legacy: writes + formats if DB path unavailable |

The `article_processor` system prompt uses **prompt caching** (`cache_control: {"type": "ephemeral"}`), reducing cost on repeated runs. The system prompt is the same across all 5 topic calls in one pipeline run, so cache hits are expected for calls 2–5.

### Duplicate Detection

The article processor receives a "recently covered stories" list as context:
- **Primary source**: `approved_articles` table — titles from the last 7 days, formatted as `[YYYY-MM-DD / topic] Title`
- **Secondary source**: `history/newsletter_history.json` — headline strings from the last 7 days

These two sources are merged; approved_articles context takes precedence (it reflects what was actually published, whereas the JSON file only updated on send and was stale during development).

Claude classifies each story as `new` / `followup` / `duplicate`. "Followup" requires a **materially new fact** (a number changed, a decision was made, a new actor entered, an outcome announced). More reporting on the same situation without new facts is classified as `duplicate`. When uncertain between followup and duplicate, Claude is instructed to choose `duplicate`.

---

## Score-Based Article Routing

After human review, `newsletter.py` splits approved articles into two pools:

| Pool | Criteria | Used for |
|---|---|---|
| Full section | `score_importance ≥ 2 AND score_interest ≥ 2` | Main section write-ups |
| Demoted | `score_importance < 2 OR score_interest < 2` | Quick Hits only |

A third pool feeds Quick Hits from the `articles` table:
- `status = 'pending'` (not human-reviewed)
- All three `ai_confidence_*` scores ≥ 4
- `title IS NOT NULL` (processed by pipeline)

Claude picks the 5 most interesting Quick Hits from the combined demoted + high-confidence pending pool.

---

## Supabase Schema

Six tables. All reads/writes use the service role key (no RLS for pipeline scripts; RLS is enforced for the PWA/Vercel frontend).

```
sources          — one row per section (source_id FK in articles)
articles         — raw + AI-processed articles; lifecycle state machine
approved_articles — copy of approved articles; read by PWA + newsletter
daily_briefs     — one row per day; brief card content
human_reviews    — every safety-gate + calibration decision (training data)
processing_log   — every Claude API call (tokens, cost, latency)
```

`approved_articles.rank_score` is a **generated column**: `score_importance * 2 + score_urgency + score_interest`. The PWA and newsletter both order by `rank_score DESC`.

`approved_articles.published_at` is stamped **only when `send_mode="send"`** — draft runs are idempotent and do not consume articles from the pool.

---

## GitHub Actions Workflow

File: `.github/workflows/newsletter.yml`

Runs at `0 15 * * *` (8:00 AM PDT / 15:00 UTC). Can be triggered manually with a `send_mode` input (`draft` | `send`).

```
Steps:
  1. Checkout repo
  2. Setup Python 3.12
  3. pip install dependencies
  4. sync_subscribers.py — pull latest signup/unsub from Google Sheets
  5. pipeline.py         — fetch + AI process (writes to Supabase)
  6. newsletter.py       — render + send (reads from Supabase)
  7. git commit history/ subscribers.json docs/
  8. git push
  9. Failure notification (GitHub Actions)
```

The pipeline and newsletter steps both receive `TZ: America/Los_Angeles` so `date.today()` in Python resolves to Pacific time.

Human review (`review_cli.py`) is run locally, **between** pipeline.py and newsletter.py, before the scheduled send. In practice: pipeline runs at 8 AM, review happens at 8–9 AM, and the newsletter can be re-triggered manually post-review with `send_mode=send`.

---

## Frontend (PWA / Vercel)

A Next.js app deployed on Vercel (Hobby tier, free). Uses the Supabase JS client with RLS. Reads from `approved_articles` and `daily_briefs`.

Card deck UX:
- Card 1: Daily brief (from `daily_briefs WHERE brief_date = today AND approved_at IS NOT NULL`)
- Cards 2–N: Articles sorted by `rank_score DESC LIMIT 10`
- Detail view: `detail_summary` field (300–400 words, generated by pipeline alongside `balanced_summary`)
- End card: closed-ended; no infinite scroll

The PWA does not participate in the pipeline. It is a read-only consumer of the Supabase DB.

---

## Publishing

**Email**: Brevo transactional API (`/v3/smtp/email`). Each subscriber receives a personalized email (name substitution, per-recipient unsubscribe link). On failures, an admin alert goes to the owner's Gmail via SMTP.

**Web archive**: `docs/issues/YYYY-MM-DD.html` per issue; `docs/issues/index.json` index. Served as GitHub Pages. Kept 90 days.

**SEND_MODE logic**: The `SEND_MODE` env var (from the `SEND_MODE` secret or manual workflow input) controls whether emails are sent. Default is `draft` (HTML saved, no send). Set to `send` in the secret for the scheduled daily run.

---

## Cost Model

| Component | Calls/day | Est. monthly |
|---|---|---|
| pipeline.py — article_processor (5 topics) | 5 | ~$4.50 |
| pipeline.py — brief_generator | 1 | ~$0.25 |
| newsletter.py — approved_newsletter layout | 1 | ~$0.75 |
| Supabase (free tier) | — | $0 |
| Vercel (Hobby tier) | — | $0 |
| Tavily (1000 searches/month included) | ~5/day | $0 |
| Brevo (300 emails/day free) | ~5–50/day | $0 |
| **Total** | | **~$6–8/month** |

`processing_log` records every Claude call with token counts and estimated cost for monitoring.
