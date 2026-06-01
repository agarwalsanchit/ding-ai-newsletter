# DING.AI — Architecture

> Last updated: May 21, 2026
> Reflects the two-script pipeline (pipeline.py + newsletter.py) and PWA frontend (Phase 2 complete).

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
                        │       conf ≥3 all axes               │
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
| 🎾 Sports & Entertainment | Keyword-rich query (Champions League, UEFA, Premier League, La Liga, IPL cricket, NBA, NFL, F1, tennis, Grand Slam). The old `site:` wire-service restriction was dropped — it hid legitimate match recaps; the URL blocklist still filters boxscores/live-score pages |
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
   │      all 3 axes ≥ 3 → auto_approved │
   │      any axis < 3   → pending       │
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
                   (has RLS: anon can only read high-confidence pending rows)
approved_articles — copy of approved articles; read by PWA + newsletter (no RLS)
daily_briefs     — one row per day; brief card content
translations     — Hindi translations per approved_article_id (no RLS)
human_reviews    — every safety-gate + calibration decision (training data)
processing_log   — every Claude API call (tokens, cost, latency)
```

`approved_articles.rank_score` is a **generated column**: `score_importance * 2 + score_urgency + score_interest`. The PWA and newsletter both order by `rank_score DESC`.

Key fields added since initial schema:
- `articles.article_brief` — 40-60 word card-face brief (added May 2026)
- `articles.detail_summary` — 300-400 word detail view text
- `articles.ai_confidence_factual/on_topic/source` — per-axis confidence (1-5); gate for RLS + auto-approval
- `approved_articles.article_brief` — copied from `articles.article_brief` at approval time
- `approved_articles.left_perspective / right_perspective` — Phase 3 fields (null until generated)

`approved_articles.published_at` is stamped **only when `send_mode="send"`** — draft runs are idempotent and do not consume articles from the pool.

---

## GitHub Actions Workflow

File: `.github/workflows/newsletter.yml`

Runs at `0 15 * * *` (8:00 AM PDT / 15:00 UTC). Can be triggered manually with a `send_mode` input:

| send_mode | Effect |
|---|---|
| `pipeline_only` | Runs pipeline.py only — fetches + processes articles, updates Supabase. Skips newsletter.py entirely. **Default for manual triggers.** Use this to refresh the PWA without sending email. |
| `draft` | Runs pipeline.py + newsletter.py. Renders HTML email but does not send. |
| `send` | Runs pipeline.py + newsletter.py. Sends email to all subscribers. Used by the scheduled run. |

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

A Next.js app deployed on Vercel (Hobby tier, free). Uses the Supabase JS client with RLS (anon key). Reads from `approved_articles`, `daily_briefs`, and high-confidence pending rows from `articles`.

**Date logic**: "today" is computed as Pacific time using `Intl.DateTimeFormat('en-CA', { timeZone: 'America/Los_Angeles' })` in Next.js server components. This matches the pipeline's timezone (`TZ: America/Los_Angeles` in GH Actions). Articles from a **two-day window** (today + yesterday, Pacific) are shown: most stories fetched at 8 AM PT were published the previous day, so a today-only filter hid almost everything — the window also tolerates a late or missed pipeline run.

**Dual-source article query** (runs server-side in `page.tsx`):
1. `approved_articles WHERE article_date >= yesterday ORDER BY rank_score DESC LIMIT 10` — human or ai-auto-approved (two-day window)
2. `articles WHERE article_date >= yesterday AND status = 'pending' AND ai_confidence_factual >= 4 AND ai_confidence_on_topic >= 4 AND ai_confidence_source >= 4` — high-confidence pending in the two-day window (no human review; access via RLS policy)

Both sources are merged and de-duplicated (articles already in `approved_articles` are dropped from the pending pool), then the 10-card deck is built with a **topic-diversity cap**: a first pass takes up to `PER_TOPIC_CAP` (2) of each topic in rank order, and a second pass backfills any remaining slots by rank regardless of topic. This stops a prolific category (e.g. finance) from flooding the deck while still filling it on a slow news day. Translations are only fetched for approved articles (the `translations` table is keyed on `approved_article_id`).

Card deck UX:
- Card 1: Daily brief (most recent approved `daily_briefs` in the two-day window: `approved_at IS NOT NULL AND brief_date >= yesterday ORDER BY brief_date DESC LIMIT 1`); shows empty state if no articles, or an error state if the fetch failed
- Cards 2–N: Articles sorted by `rank_score DESC LIMIT 10`; card text uses `article_brief ?? balanced_summary`
- Detail view: `detail_summary` (300–400 words), "Why it matters" as accent callout, language toggle (EN/HI)
- End card: closed-ended; no infinite scroll
- Topic filter: settings panel lets user deselect topics; filtered out of visible deck. Brief-card topic chips are tappable and jump to that topic's first story
- Splash screen: ~4.5s entry animation on first visit per browser session (tap to skip); respects `prefers-reduced-motion`

**RLS policies relevant to the PWA (anon key)**:
- `approved_articles`: no RLS — publicly readable
- `daily_briefs`: anon can SELECT where `approved_at IS NOT NULL`
- `articles`: anon can SELECT where `status = 'pending' AND ai_confidence_factual >= 4 AND ai_confidence_on_topic >= 4 AND ai_confidence_source >= 4 AND title IS NOT NULL` (policy: `anon_read_high_confidence_pending`)
- `translations`: no RLS — publicly readable

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
