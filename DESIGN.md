# DING News App — Design Document

> Companion to `ARCHITECTURE.md` (which describes the current newsletter system).
> This document describes the **new** system being built on top of it.
>
> Last updated: May 21, 2026 (Phase 2 frontend complete)
> Status: Phase 2 backend + frontend shipped. Topic filtering (Phase 4) shipped. PWA live on Vercel.

---

## 1. Purpose

DING.AI today is a daily newsletter: one AI-generated HTML email per day, sent via Brevo. The next iteration is a **multi-language reader app** for the same content — but more specifically, it's a **glanceable daily ritual**, not a scrolling feed.

The product is designed around a single user behavior: **10 minutes over morning coffee to be mostly up to date.** Everything in the system serves that ritual. Closed-ended deck (not infinite scroll), one article per screen (not a list), TLDR by default (full content one tap away), signal over noise.

Goals, in priority order:
1. **Learn AI system design** — the app is a vehicle for learning how to build production-grade AI pipelines with appropriate human oversight.
2. **Become the user's morning news ritual** — for Sanchit first, his family second (in Hindi later), close friends third. Time-boxed, satisfying, complete.
3. **Preserve newsletter parity** — existing subscribers should see no degradation; the newsletter is a downstream consumer of the same article database.

Explicit non-goals: multi-perspective framing (left/right) — Phase 4. Push notifications. Native iOS/Android. User accounts beyond magic-link auth. Topic personalization — Phase 3.something. Images — Phase 5+. Infinite content. Engagement metrics. Sharing primitives.

---

## 2. Product model: the daily deck

The app is a **vertical card deck**, not a feed. Each card is one screen. Navigation is gesture-based: swipe up to advance to the next card, tap to drill into detail.

### 2.1 Deck composition

A normal deck for a given day:

```
Card 1 (always):  Today's brief
Card 2:           Article 1 (highest rank_score)
Card 3:           Article 2
...
Card N:           Article N-1
Last card:        "That's the signal for today. See you tomorrow."
```

Card count target: **7-10 articles per day**, plus the brief card and the end card. Total deck depth typically 9-12 cards. On a slow news day, the system shows fewer cards rather than padding with weak articles — the deck is closed-ended by design.

Cards are selected from `approved_articles WHERE article_date = today ORDER BY rank_score DESC LIMIT 10`. If fewer than 5 approved articles exist for the day, the deck still ships but with whatever's available — a "light news day" state is acceptable, padding is not.

### 2.2 The brief card (Card 1)

Always the first card. Generated daily by Sonnet from the day's approved articles. Structure:

```
Today's date (e.g., "SUNDAY, MAY 17")
"Good morning."  or similar editorial opener
2-3 sentence brief covering the day's top stories, in the voice of the
   existing newsletter intro paragraph
"X stories ahead. Let's get into it." or similar transition
Topic chips: small mono labels for the topics in today's deck
```

The brief card is the editorial anchor of the app. Without it, the deck is a sorted list. With it, the deck is a publication. This card is Phase 1 of the UI — non-optional.

For first-time users, the brief card additionally renders a brief one-line "what is DING News?" tagline above the standard brief content.

**Empty state**: If the pipeline hasn't run yet for today (no articles available), the brief card shows "Today's deck isn't ready yet. Check back after 8 AM Pacific." The swipe-up affordance is hidden when the deck is empty — there is nothing to navigate to.

### 2.3 Article cards (Cards 2 to N)

One article per card. The full card fits one mobile screen with no internal scrolling. Reading the full card should be possible in under 30 seconds.

Card anatomy, top to bottom:

```
Metadata line:    [Topic name in muted mono]  ·  [Date]  ·  [Source domain]
Headline:         Inter, ~26-28px, weight 600, line-height 1.15
Article brief:    40-60 word card-face brief (article_brief field). Key facts only:
                  who/what/when/where. No "Why it matters," no background context.
                  First sentence carries the most important fact. Written to fit one
                  mobile screen without truncation. Falls back to balanced_summary
                  for articles processed before the article_brief field was added.
Affordance hint:  "Tap to expand" in --subtle color, inline directly below the text.
                  Not absolute positioned — no overlap with content.
```

"Why it matters" is NOT shown on the card face. It appears only in the detail view (see 2.4). The card is glanceable — one fact per screen, tap for depth.

### 2.4 Detail view (one tap deeper)

Tapping the headline (or anywhere on the card body except the source domain) opens an expanded view of the article. Default shape (Decision J option A):

**A longer-form version of the same balanced summary, ~300-400 words**, generated by Sonnet at processing time and stored on the approved article. Same shape as the summary, just more depth — additional context, more named entities, more concrete numbers. No new sections, no perspectives, no source quotes (those come in later phases).

"Why it matters" appears in the detail view as an accent left-border callout block:
- Left border: 2px solid `var(--accent)` 
- Label: "WHY IT MATTERS" in accent color, mono font, 10px — or the Hindi equivalent ("यह क्यों मायने रखता है") when language is toggled
- Body: same `var(--text)` as article text, 15px, line-height 1.55
- Not italic — accent border provides the visual distinction

Detail view UX:
- Slides up over the card (or fades in over it) — does NOT navigate to a new route
- Has a clear close affordance (X in top-right, or swipe down to dismiss)
- Scrolls internally if content exceeds screen height
- The source URL is a tap target inside the detail view as well as on the card
- Returning from detail view restores the card deck position exactly

### 2.5 The source link

Tapping the source domain (in the metadata line on the card OR on the detail view) opens the original article in the device's default browser. NOT in an in-app webview — we don't want to obscure that the user is leaving DING. Editorial transparency: "this is our summary, here's the actual source."

### 2.6 End card

Reached after the last article card. Single message:

```
That's the signal for today.
See you tomorrow morning.
[Optional: cost-of-attention nicety, e.g., "Took you 7 minutes."]
```

No "load more," no related-articles, no engagement hooks. Closed-ended is the point.

### 2.7 Navigation gestures

| Gesture | Action |
|---|---|
| Swipe up | Advance to next card |
| Swipe down (on a card) | Go back to previous card |
| Tap card body | Open detail view |
| Tap source domain | Open original article in browser (new tab) |
| Swipe down (in detail view) | Close detail view, return to card |
| Tap X (in detail view) | Close detail view, return to card |

Edge behavior: swipe up on the end card does nothing (already at end). Swipe down on the brief card does nothing.

### 2.8 What this product is NOT

- An infinite feed
- A scrolling reader
- A magazine-style site
- Something to read for an hour
- A social platform
- A bookmark/save app
- A search engine for news

Decisions that contradict the daily-ritual model should be rejected unless they explicitly redefine the model. The 10-minute closed-ended ritual is the product.

---

## 3. The core design principle: human + AI, not AI alone

(unchanged from prior draft — preserved)

A good AI product is a thoughtful split of labor:

| Layer | What AI does well | What only humans should do |
|---|---|---|
| Source selection | Crawl and dedupe at scale | Decide which sources count as credible |
| Topic clustering | Group similar articles | Flag which topics need balanced framing |
| Synthesis | Draft summaries fast | Verify nothing was hallucinated |
| Perspectives | Frame left/right views from coverage | Confirm the framing isn't a strawman |
| Translation | Translate to Hindi/Marathi | Catch cultural and political nuance |
| Informed positions | Surface credible voices | Approve any position before it ships |
| Brief generation | Synthesize day's news into intro | Approve the brief before publish |

Every phase names the human gate explicitly. Review is teaching, not just blocking.

---

## 4. Design rules

(unchanged from prior draft — preserved verbatim)

### 4.1 Source of truth
Tavily owns `topic`, `published_date`. Claude owns generated text. Python orchestrates.

### 4.2 Human gate placement
Store everything; display only approved.

### 4.3 Batching at granularity of relative judgment
Per-topic, not per-article. Six Sonnet calls per day for article processing.

### 4.4 Every human gate produces training data
Review captures what, and why. Disagreement data is more valuable than the gate itself.

### 4.5 Reference structured input by index, not content
LLMs return integer indices into Python-controlled input lists. Indices are validatable; restated content is hallucinatable.

### 4.6 Closed-ended is a feature, not a limitation [NEW]

The product is a daily ritual measured in minutes, not articles. Every design decision is evaluated against: *does this serve the 10-minute closed-ended ritual?* Infinite scroll, "load more," and engagement loops are explicitly rejected. The deck ends. The end card is the goal, not a failure.

This rule constrains all future feature decisions. When in doubt: closed wins over open, fewer wins over more, depth-on-tap wins over depth-on-screen.

---

## 5. Pipeline flow (daily run)

**Phase 2 implementation note**: Steps 1–7 run in `pipeline.py`; steps 8–10 run in `newsletter.py`. Human review (step 7b) runs locally via `review_cli.py` between the two scripts.

```
pipeline.py:
1. Context           → Pull approved_articles (last 7 days) + history JSON
                       as recent-coverage context for Claude duplicate detection
2. Fetch             → 5 Tavily queries × up to 10 articles = ~50 raw articles
                       (no dedicated Top News query — Top News is a computed flag)
3. Persist           → URL dedup (2-day window) + Tavily score filter (≥0.4)
                       + URL blocklist (video/boxscore/podcast pages)
                       → articles table (status=pending)
4. Idempotency       → Re-fetch only articles still status=pending today
5. Process           → 5 Sonnet calls (per topic), each returns JSON array
                       with source_indices, scores, ai_confidence,
                       relationship_to_recent, balanced_summary, detail_summary,
                       why_it_matters
6. Route             → per article:
                          - "duplicate"                → auto_rejected
                          - all ai_confidence==5       → auto_approved + approved_articles
                          - any ai_confidence<5        → pending (human review)
7. Flag Top News     → pick highest (score_importance + score_urgency) article
                       from today's approved + pending pool; update topic
                       to "🚨 Top News" in both articles + approved_articles
8. Brief generation  → 1 Sonnet call: read today's approved articles,
                       generate brief card content; insert into daily_briefs

[human review window — review_cli.py runs locally]
7b. Safety gate      → 5 yes/no questions per pending article
7c. Calibration      → optional AI score vs. human score comparison
7d. Brief review     → single question on brief accuracy

newsletter.py:
9. Score demotion    → approved articles with importance<2 OR interest<2
                       are demoted from full sections to Quick Hits pool
10. Quick Hits pool  → demoted approved + high-confidence pending
                       (all ai_confidence ≥ 4)
11. Render           → 1 Sonnet layout call: formats approved content into
                       HTML email template (no content invention)
12. Send             → Brevo API (if send_mode=send); stamp published_at
13. Archive          → docs/issues/YYYY-MM-DD.html + index.json
14. Translate        → Phase 3: Hindi translation per approved article
15. Publish          → newsletter reads from approved_articles;
                       PWA reads from:
                         - approved_articles (WHERE article_date = today)
                         - articles WHERE status='pending' AND all
                           ai_confidence axes >= 4 (high-confidence pending)
                       Merged, sorted by rank_score DESC, LIMIT 10.
                       If no articles for today: empty state on brief card.
```

**Key architectural decisions captured here:**
- Top News is computed from scores, not fetched from a dedicated Tavily query — a dedicated "breaking news" query reliably returned video pages and aggregator content, not articles.
- Duplicate detection is authoritative: Claude receives approved_articles titles (what we actually published) as the ground truth, not just headlines from the JSON history file (which only updated on send).
- "Followup" requires a materially new fact. More reporting on the same situation without new facts is classified as "duplicate" — when uncertain, choose duplicate.
- Quick Hits draws from two pools (demoted approved + high-confidence pending) so high-quality articles that didn't pass human review can still surface in a lower-trust format.

### 5.1 Cross-topic feed ranking

Same formula as before: `rank_score = importance × 2 + urgency × 1 + reader_interest × 1`. Used to sort the deck. Top 7-10 by rank_score become cards 2 to N.

---

## 6. Database schema

(preserved from prior draft with two additions)

### 6.1 - 6.5 (unchanged)

`sources`, `articles`, `approved_articles`, `translations`, `human_reviews`, `processing_log` — see prior draft for full schemas.

### 6.6 [UPDATED] `approved_articles` — add detail_summary and article_brief fields

```diff
  approved_articles
  - id                 uuid, PK
  - article_id         uuid, FK
  - topic              text
  - article_date       date
  - title              text
+ - article_brief      text     -- 40-60 words; card-face primary text
  - balanced_summary   text     -- 100-120 words; fallback if article_brief null
+ - detail_summary     text     -- 300-400 words; detail-view-facing
  - why_it_matters     text     -- shown in detail view only (accent callout)
  - score_importance   smallint
  - score_urgency      smallint
  - score_interest     smallint
  - rank_score         numeric (generated)
  - source_urls        text[]
  - approved_at        timestamptz
  - approved_by        text
  - published_at       timestamptz
```

`article_brief` is generated in the same Sonnet call as `balanced_summary`. It's nullable for rows processed before this field was added; the PWA falls back to `balanced_summary` when null.

`detail_summary` is generated in the same Sonnet call as `balanced_summary` to amortize cost. It's nullable for backfilled rows where detail wasn't generated.

### 6.7 [NEW] `daily_briefs`

One row per day. Generated by step 6 of the pipeline. Read by the PWA as Card 1 of the deck.

```
daily_briefs
- id                  uuid, PK
- brief_date          date, UNIQUE
- editorial_opener    text       -- e.g., "Good morning." or context-aware variant
- brief_body          text       -- 2-3 sentence summary of the day
- transition_line     text       -- e.g., "8 stories ahead. Let's get into it."
- topic_chips         text[]     -- ordered list of topics in today's deck
- generated_at        timestamptz
- approved_at         timestamptz, nullable -- requires human review like articles
- approved_by         text, nullable -- 'human' | 'ai_auto'
- ai_confidence       smallint, 1-5 -- self-rated by Sonnet, basis for auto-approval
```

Same auto-approval rules as articles: confidence 5 → auto-approved.

---

## 7. Prompts

(preserved from prior draft with updates to 7.1; new 7.2)

### 7.1 [UPDATED] Article processor — adds detail_summary field

The per-topic batch prompt now requests three summary lengths per article:

```diff
For each distinct news event in the input list, produce a JSON object 
with these fields:

  - "source_indices": ...
  - "title": ...
+ - "article_brief": 40-60 words. Card-face brief — the first thing a 
+   reader sees. Key facts only: who/what/when/where. No "why it matters,"
+   no background context. First sentence carries the most important fact.
+   Must fit one mobile screen without truncation.
- - "balanced_summary": 100-120 words ...
+ - "balanced_summary": 100-120 words for the glanceable card view ...
+ - "detail_summary": 300-400 words for the detail view. Same balanced 
+   tone and source-grounding as balanced_summary, but with more 
+   context: additional named entities, concrete numbers, background 
+   context that helps a reader who wants depth. Do NOT add new claims 
+   not supported by the source excerpts.
  - "why_it_matters": ...
  - "score": ...
  - "ai_confidence": ...
  - "relationship_to_recent": ...
```

### 7.2 [NEW] Brief generator

Called once per day after article processing completes. Single Sonnet call.

```
You are the editor of DING News, a daily news app for readers who want 
to be informed in under 10 minutes. Today's deck has been finalized — 
your job is to write the brief card that opens the deck.

Input: the day's approved articles (titles + balanced_summary + topic) 
in the order they will appear (sorted by rank_score DESC).

Produce a JSON object with these fields:

- "editorial_opener": one short opener. "Good morning." is the default. 
  Vary it occasionally for tone — "Heavy news day." on weeks with major 
  events; "Quieter Tuesday." on slow days. Maximum 4 words.

- "brief_body": 2-3 sentences (40-60 words total) summarizing the day's 
  most significant stories in flowing prose. Reference 2-3 specific stories 
  by topic, not by repeating the headlines. Write in the voice of a 
  curator addressing a friend, not a wire service. Example tone:
  
  "The US-brokered Ukraine ceasefire is on life support as Russia and 
  Ukraine keep trading fire — and Trump's rejection of Iran's latest 
  peace overture is rattling energy markets across Asia. Meanwhile, 
  Wall Street is melting up anyway."

- "transition_line": one short line that hands off to the article cards. 
  Mention the count. Example: "8 stories ahead. Let's get into it."

- "topic_chips": array of topic names that appear in today's deck, in the 
  order they'll appear. No duplicates.

- "ai_confidence": 1-5, your confidence that the brief accurately 
  represents the day's articles without overstating, editorializing, or 
  missing the most important story. 5 means: no concerns, can ship 
  without human review.

Hard rules:
- Do not editorialize beyond what the articles themselves say.
- Do not introduce facts not in the input articles.
- The brief should reflect the day's actual significance, not invent drama.
- Return JSON only, no prose wrapper.

Input articles for {date}:
{indexed_articles}
```

### 7.3 Hindi translation, Marathi (Phase 3+), Newsletter generator

(unchanged from prior draft)

---

## 8. Decisions log

A through I preserved. Three new decisions logged tonight.

### Decision J — Detail view is a longer summary, same shape [NEW]

When the user taps a card, the detail view shows a 300-400 word longer version of the same balanced summary, not a multi-section breakdown. Single content block, same tone, same structure as the card summary.

Rationale: simplest extension of current data model — `detail_summary` is just another field on the same table, generated in the same Sonnet call. Doesn't require schema redesign. Multi-section structure (background / facts / takes) is reserved for Phase 4 when perspectives ship.

Tradeoff accepted: detail view feels less editorially distinct than a structured-section approach would. We can revisit if reader behavior suggests it.

### Decision K — "Why it matters" moved to detail view with accent callout [UPDATED]

Originally planned as italic text on the card face. Changed: "Why it matters" is now shown only in the detail view, as a left-border accent callout (2px `var(--accent)` left border, "WHY IT MATTERS" label in accent color/mono font, body in normal `var(--text)`). Removed from the card face entirely.

Rationale: the card face should carry the news fact, not the editorial framing. The reader who wants "why it matters" is the same reader who taps for detail — so this is the right gate. The accent callout treatment is more visually distinct than italic and works in both dark and light themes without color hardcoding.

### Decision M — article_brief as primary card-face field [NEW]

The card face uses `article_brief` (40-60 words) rather than `balanced_summary` (100-120 words). The `article_brief` is written to fit one mobile screen without truncation — no `WebkitLineClamp`, no ellipsis.

Rationale: `balanced_summary` is too long for a glanceable card; truncating it produces incomplete thoughts. Generating a purpose-built shorter field lets the first sentence carry the key fact, with the rest of the card serving depth. `balanced_summary` becomes a fallback for rows processed before this field was added.

### Decision N — Today-only date, no fallback to older dates [NEW]

The PWA shows only articles where `article_date = today` (Pacific time). If no articles exist for today, the brief card shows an empty state ("Today's deck isn't ready yet. Check back after 8 AM Pacific."). There is no fallback to yesterday's or last week's articles.

Rationale: showing stale articles from previous days creates a misleading signal — the reader doesn't know if they're seeing yesterday's news or today's. An honest empty state is better than inflated-but-stale content. The deck is a daily ritual; stale content breaks the ritual's promise.

Timezone note: `article_date` is stamped in Pacific time (GH Actions runs with `TZ=America/Los_Angeles`). The PWA must use the same timezone (`Intl.DateTimeFormat('en-CA', { timeZone: 'America/Los_Angeles' })`) to compute "today" — otherwise articles fetched at 11 PM PT appear on tomorrow's date in UTC.

### Decision O — High-confidence pending articles surface in PWA without human review [NEW]

The PWA queries two sources for its article pool:
1. `approved_articles WHERE article_date = today` — human or auto-approved
2. `articles WHERE status = 'pending' AND ai_confidence_factual >= 4 AND ai_confidence_on_topic >= 4 AND ai_confidence_source >= 4 AND article_date = today` — high-confidence pending (no human review)

These are merged, sorted by rank_score, and capped at 10.

Rationale: without this, the deck showed yesterday's articles until a human ran `review_cli.py` — which could be hours after the pipeline ran. High-confidence pending articles (all three ai_confidence axes ≥ 4) have demonstrated AI quality sufficient for the newsletter's Quick Hits pool; showing them directly in the deck is a reasonable trust extension given the PWA's low-stakes context.

Access is controlled via Supabase RLS: a specific policy on the `articles` table allows the anon key to read only rows that satisfy the confidence thresholds. The pipeline uses the service role key (bypasses RLS) and is unaffected.

Tradeoff accepted: articles surfaced this way may not have been human-reviewed. They carry `approved_by: 'ai_auto'` in the frontend's representation but this is not currently surfaced to readers. If reader-facing quality concerns emerge, the threshold should be raised (≥5 on all axes = auto_approved territory) rather than reverting to human-review-only.

### Decision L — Card-deck UX with swipe navigation [NEW]

The PWA renders as a vertical card deck (one card per article) with gesture-based navigation, not a scrolling feed. Brief card opens the deck; end card closes it. Detail view is a modal overlay, not a route change.

Rationale: aligns the interaction model with the product vision (10-minute daily ritual, closed-ended, glanceable). A scrolling feed contradicts the "signal over noise" thesis at the interaction level — infinite scroll is noise architecture.

Implementation implications: Framer Motion (or similar) for swipe handling and card transitions. Modal pattern for detail view. State for "current card index" persisted in URL hash so refreshing the page restores position. These are the substantive frontend tasks for the next phase of UI work.

### Decisions A-I (preserved)

A. `approved_articles` as copy, not reference  
B. Hindi Phase 3, Marathi Phase 5  
C. Per-topic batching  
D. CLI review tool  
E. Prompt caching from day one  
F. Auto-approve confidence 5-5-5 articles  
G. URL exact dedup + Sonnet-judged similarity  
H. Cross-topic rank formula: importance × 2 + urgency + interest  
I. UI detour pre-Yellowstone with seeded data

---

## 9. Human review

(preserved — safety gate + calibration, with one addition)

### 9.1 - 9.4 (unchanged)

### 9.5 [NEW] Brief card review

The daily brief gets its own review pass, separate from article-level review. Question:

- Does the brief accurately represent today's deck without overstating, missing the lede, or editorializing beyond the articles themselves?

Single blocking question. If failed, the brief is rejected and regenerated. Auto-approval available at ai_confidence 5.

---

## 10. Cost model

Updated for new pipeline shape:

| Component | Calls/day | Est. cost/month |
|---|---|---|
| Article processor (per-topic batch with detail_summary) | 6 | $6.50 |
| Brief generator | 1 | $0.50 |
| Hindi translation (per approved article) | ~10 | $2.25 |
| Newsletter generator (refactored) | 1 | $1.00 |
| Supabase (free tier) | — | $0.00 |
| Vercel hosting (free tier) | — | $0.00 |
| **Total** | | **~$10/month** |

`detail_summary` increases the article processor output by ~3x in word count, bumping monthly cost ~$2. Still well under $20/month total.

---

## 11. UI roadmap

### Phase 1 (current — pre-Yellowstone DONE, post-Yellowstone REBUILD)
- Brief card (Card 1)
- Article cards (Cards 2 to N, sorted by rank_score, limit 10)
- Detail view on tap (longer summary)
- Source link opens original article in browser
- End card
- Swipe navigation between cards
- English only

### Phase 2 (after Phase 1 ships)
- Translation toggle per card (English / Hindi)
- Reader's chosen language persists across sessions

### Phase 3
- Left-leaning and right-leaning perspectives as additional content blocks within detail view
- Visual indication on the card that perspectives are available

### Phase 4
- Topic preferences: user selects which topics enter their deck
- Decks may be customized per user (deferred until there are multiple users)

### Phase 5+
- Article images (license complications; deferred)
- Audio reading mode
- Eventual podcast
- Native iOS/Android shell (only if PWA proves limiting)

---

## 12. Open questions

- [ ] **Detail view: modal vs new route.** Modal feels more "stays inside the deck"; route change preserves browser back-button. Decide during Sitting 5 implementation.
- [ ] **First-time user education.** Does Card 1 need a one-line "what is DING" tagline for new users only, or is the experience self-explanatory? Test with Sudeep first.
- [ ] **Card position persistence.** If a user closes the app mid-deck and reopens an hour later, do they resume mid-deck or restart from the brief? Strong intuition: resume mid-deck.
- [ ] **Brief regeneration on edits.** If an article is rejected after the brief is generated, does the brief regenerate, or does it stay stale? Default: stays stale unless 2+ articles are rejected, then regenerate.
- [ ] **Beta tester list.** Sudeep, Vaishnavi, plus 3-5 family members for Hindi review.

---

## 13. Phase 2 backend task list

(updated to reflect the card-deck model)

- [x] **2.0** Verify Tavily output schema
- [x] **2.1** Supabase schema migration (initial 6 tables)
- [x] **2.2** `persist_fetched_articles` with URL dedup + Tavily score filter
- [x] **2.3** URL pre-filter (folded into 2.2; expanded with 13-pattern blocklist for video/boxscore/podcast pages)
- [x] **2.4** Article processor: 5 Sonnet calls per topic (pipeline split from newsletter; includes `detail_summary`; max_tokens=8192)
- [x] **2.4b** Schema migration: `detail_summary` on `approved_articles`; `daily_briefs` table; `processing_log` table
- [x] **2.5** `source_indices` orchestration (folded into 2.4; secondary articles marked `auto_rejected`)
- [x] **2.6** Auto-approval routing (duplicate→auto_rejected; all-5-confidence→auto_approved; else pending)
- [x] **2.7** `processing_log` writes around every Sonnet call (tokens, cost, latency)
- [x] **2.7b** Brief generator: 1 Sonnet call per day from approved articles; upserts `daily_briefs`
- [x] **2.7c** [NEW] `flag_top_news()`: computed Top News flag from highest importance+urgency article
- [x] **2.7d** [NEW] Supabase-sourced duplicate context: approved_articles (last 7 days) as authoritative recent-coverage list
- [x] **2.7e** [NEW] Score-based article demotion: importance<2 OR interest<2 → Quick Hits pool only
- [x] **2.7f** [NEW] Two-pool Quick Hits: demoted approved + high-confidence pending (all ai_confidence≥4)
- [x] **2.8** CLI safety-gate tool with the 5-question checklist + brief review (`review_cli.py`)
- [x] **2.9** CLI calibration tool (with dedup: skips already-calibrated articles across sessions)
- [x] **2.10** End-to-end test (pipeline.py → review_cli.py → newsletter.py verified in production)
- [x] **2.11** Refactor newsletter to read from `approved_articles` (draft mode idempotent: no `published_at` stamp)
- [x] **2.12** Verify production newsletter still sends
- [x] **2.13** Phase 2 retrospective commit

## 14. Phase 2 frontend task list

(new — replaces the abandoned scrolling-list UI direction)

- [x] **F2.1** Next.js scaffold, Supabase wired, RLS locked down
- [x] **F2.2** Vercel deployment + PWA install (current prod)
- [x] **F2.3** Install Framer Motion; build card-deck primitive (one full-screen card, swipe up/down handlers, card-stack visual transition)
- [x] **F2.4** Build brief card component, wire to `daily_briefs` table; empty state when no articles
- [x] **F2.5** Build article card component using `article_brief ?? balanced_summary`; inline "Tap to expand" affordance; no truncation
- [x] **F2.6** Build detail view modal (slides up over card, swipe-down to dismiss, scrolls internally); "Why it matters" accent callout
- [x] **F2.7** Source domain tap opens external link
- [x] **F2.8** End card
- [x] **F2.9** Card position persistence via URL hash (deck#card-3)
- [x] **F2.10** Mobile gesture polish (momentum, snap, edge resistance)
- [x] **F2.11** Replace current scrolling feed page with new deck
- [x] **F2.12** Language toggle (English / Hindi) per card and in detail view
- [x] **F2.13** Topic filter settings panel (Phase 4 shipped alongside frontend)
- [x] **F2.14** Splash screen with slow entry animation (~4.5s total before deck)
- [x] **F2.15** High-confidence pending articles surfaced in PWA (RLS policy + dual-source query in page.tsx)
- [x] **F2.16** Today-only date logic, Pacific timezone, empty state when pipeline hasn't run

---

*Re-read Section 2 (product model) when in doubt. Re-read Section 4 (design rules), especially 4.6 (closed-ended is a feature), when tempted to add infinite-scroll behavior or engagement loops.*
