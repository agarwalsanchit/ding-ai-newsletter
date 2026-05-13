# DING News App — Design Document

> Companion to `ARCHITECTURE.md` (which describes the current newsletter system).
> This document describes the **new** system being built on top of it.
>
> Last updated: May 12, 2026 (Day 2, evening revision)
> Status: ready to commit; revise during Phase 2 as implementation reveals issues

---

## 1. Purpose

DING.AI today is a daily newsletter: one AI-generated HTML email per day, sent via Brevo. This document describes the next iteration — a **multi-language reader app** that consumes news from the same Tavily pipeline but processes each article into a structured, reviewable, translatable record.

The newsletter does not go away. After this redesign, the newsletter becomes a *consumer* of the new article database, selecting the day's best-scored articles and formatting them for email. The app is a parallel consumer, displaying the same articles in a phone-friendly PWA.

Goals, in priority order:
1. **Learn AI system design** — the app is a vehicle for learning how to build production-grade AI pipelines with appropriate human oversight.
2. **Serve family in Hindi (and later Marathi)** — make trustworthy news accessible to readers who currently get either biased Indian-language news or English-only quality news.
3. **Preserve newsletter parity** — existing subscribers should see no degradation; ideally, the newsletter gets *better* because article quality scoring is now explicit.

Explicit non-goals for the first build: multi-perspective framing (left/right), informed positions, user accounts beyond magic-link auth, push notifications, native mobile apps. Some of these come back in Phase 3+.

---

## 2. Architecture overview

Five layers, top to bottom:

1. **Sources** — Tavily Search API. Unchanged from current. Six topic queries.
2. **Fetch** — GitHub Actions cron job, daily at 8:00 AM PDT. Unchanged orchestration; updated to write to Postgres instead of flat files.
3. **AI Processing** — Sonnet 4.6, called **once per topic** (6 calls/day) to produce structured per-article JSON with embedded confidence scores.
4. **Storage** — Supabase Postgres. Six tables (see Section 5). Replaces all flat-file storage.
5. **Human Review Gate** — between Storage and Display. Two modes: a *safety gate* (blocking, fast, mandatory for full review) and a *calibration mode* (optional score overrides that become training data). AI-confident articles auto-approve when human bandwidth is low.
6. **Display** — two consumers of `approved_articles`:
   - PWA reader (Phase 4)
   - Newsletter generator (existing, refactored to read from the published table)

Refer to `docs/design/data-flow-v1.jpg` for the hand-drawn diagram.

---

## 3. Design rules

These are the transferable lessons identified during design. Apply them when in doubt.

### 3.1 Source of truth

Every piece of data lives in exactly one place. Tavily owns `topic`, `published_date`, and `tavily_id`. Claude owns generated text fields (rewritten title, balanced summary, why_it_matters, score). Python is the orchestrator that passes values between them.

Never ask an LLM to copy or restate data that another system already produced. LLMs are expensive data-passthrough tools, and they occasionally hallucinate plausible-looking restatements.

### 3.2 Human gate placement

Store everything; display only approved. The `articles` table holds all AI-generated drafts. The `approved_articles` table holds only what passed review (human or AI auto-approval). This gives us:
- A complete record of AI output, including rejections, for failure-mode analysis
- An immutable "what was published" record for the archive
- Clean separation: app reads only from approved tables

### 3.3 Batching at the granularity of relative judgment

Call the LLM at the smallest unit within which it can compare and rank. For news, that unit is **all articles in a topic on a given day**. Per-topic batching produces structured arrays where Claude can score `reader_interest` *relative to* the rest of the batch, isolates failures (one topic failing doesn't kill the day), and amortizes the system prompt across 4-6 articles per call.

### 3.4 Every human gate produces training data

*[Added Day 2 evening]*

Review is not just blocking; it is teaching. Always capture *why* a human disagreed with the AI, not just *that* they did. The dataset of disagreements is more valuable than the gate itself.

Concretely: every human review captures (a) the AI's original scores, (b) the human's preferred scores, (c) a short note on why. Over time this becomes labeled data for calibrating prompts, building a regressor that flags AI-score outliers, or eventually replacing parts of manual review.

Rejections matter just as much as approvals. The articles you reject + the reasons why = the most valuable signal in the system.

### 3.5 Reference structured input by index, not by content

*[Added Day 2 evening]*

When an LLM call needs to point to specific items from a list of inputs, instruct it to return integer indices, never the items themselves restated. Indices are bounded (0 to N-1), validatable (does index exist in input?), and impossible to hallucinate plausibly.

Applies broadly: "which of these inputs did you use?", "which sentence supports the claim?", "which candidate is strongest?" — all should return indices, with Python looking up the actual content from the input it already has.

---

## 4. Pipeline flow (daily run)

```
1. Fetch              → 6 Tavily queries × up to 6 articles = ~36 raw articles
2. URL dedup          → Python drops URL duplicates against last 7 days
3. Process            → 6 Sonnet calls (one per topic), each returns JSON array
                        with source_indices, scores, ai_confidence,
                        relationship_to_recent
4. Persist            → for each AI-generated article:
                          - "duplicate"  → status='auto_rejected' (still logged)
                          - "new" | "followup" + all ai_confidence==5 →
                                            status='auto_approved',
                                            copied to approved_articles
                          - "new" | "followup" + any ai_confidence<5 →
                                            status='pending' (awaits human)
5. Human review       → CLI tool, two modes:
                          - Safety gate: blocking yes/no on pending articles
                          - Calibration: optional score overrides on any
                            approved or auto-approved article
6. Translate          → for each article in approved_articles, call Sonnet
                        for Hindi translation (Phase 3+)
7. Publish            → newsletter reads approved_articles ORDER BY rank_score;
                        PWA reads approved_articles + translations
```

Phase 2 implements steps 1-5 with English only. Phase 3 adds steps 6 (Hindi). Phase 4 builds the PWA reader (step 7). Marathi and multi-perspective features land in Phase 5+.

**Cross-topic ranking formula** (step 7): `rank_score = importance × 2 + urgency × 1 + reader_interest × 1`. Importance is weighted higher because it's the most cross-topic-comparable signal. Within-topic ranking (preserved via `reader_interest`) remains available for future curated-topic feeds (e.g. "all Business this week, ranked").

---

## 5. Database schema

Postgres on Supabase. Six tables.

### 5.1 `sources`

One row per Tavily topic configuration. Static config table; rarely changes.

```
sources
- id              uuid, primary key
- topic           text, e.g. "Business & Finance"
- tavily_query    text, the query string sent to Tavily
- domain_filter   text[], optional list of domains (e.g. ["reuters.com"])
- active          boolean, default true
- created_at      timestamptz
```

### 5.2 `articles`

One row per AI-processed article. The full draft pool, including rejections and auto-approvals.

```
articles
- id                       uuid, primary key
- source_id                uuid, FK → sources.id
- source_urls              text[], URLs from matched Tavily inputs (written
                                   by Python, NOT by Claude)
- tavily_ids               text[], Tavily identifiers from matched inputs
                                   (written by Python, NOT by Claude)
- topic                    text, from sources.topic — NOT from Claude (rule 3.1)
- article_date             date, from Tavily's published_date — NOT from Claude
- title                    text, Claude-rewritten headline
- balanced_summary         text, 100-120 words from Claude
- why_it_matters           text, 1-2 sentences from Claude
- score_importance         smallint, 1-5
- score_urgency            smallint, 1-5
- score_interest           smallint, 1-5
- ai_confidence_factual    smallint, 1-5  -- AI's self-rated confidence
- ai_confidence_on_topic   smallint, 1-5
- ai_confidence_source     smallint, 1-5
- relationship_to_recent   text, enum: 'new' | 'followup' | 'duplicate'
- status                   text, enum: 'pending' | 'approved' | 'auto_approved'
                                       | 'rejected' | 'auto_rejected'
- fetched_at               timestamptz
- processed_at             timestamptz
- reviewed_at              timestamptz, nullable
```

Notes:
- `source_urls` and `tavily_ids` are arrays because per-event deduplication may merge multiple Tavily inputs into one summary (see Rule 3.5: Claude returns `source_indices`, Python derives URLs/IDs).
- `auto_rejected` means Claude flagged the article as a duplicate of recent coverage — kept for telemetry, not displayed.
- `auto_approved` means all three AI confidence scores were 5 and the article was not a duplicate.

### 5.3 `approved_articles`

One row per article that passed review (human or AI auto-approval). **Copy** of the relevant fields from `articles`, not a reference (Decision A).

```
approved_articles
- id                 uuid, primary key
- article_id         uuid, FK → articles.id, the source draft
- topic              text
- article_date       date
- title              text
- balanced_summary   text
- why_it_matters     text
- score_importance   smallint
- score_urgency      smallint
- score_interest     smallint
- rank_score         numeric, computed: importance × 2 + urgency + interest
- source_urls        text[]
- approved_at        timestamptz
- approved_by        text, enum: 'human' | 'ai_auto'
- published_at       timestamptz, when this became visible to readers
- archived_for_date  date, indexed for daily archive queries
```

`rank_score` is computed at insert time, not at query time. If the ranking formula changes (Decision H), a single SQL update backfills it.

### 5.4 `translations`

One row per (approved_article × language). Single table with a `language` column, not separate Hindi/Marathi tables.

```
translations
- id                          uuid, primary key
- approved_article_id         uuid, FK → approved_articles.id
- language                    text, enum: 'hi' | 'mr' (future: 'bn', 'ta')
- title_translated            text
- summary_translated          text
- why_it_matters_translated   text
- translated_at               timestamptz
- reviewed                    boolean, default false (light spot-check gate)
- reviewer_notes              text, nullable
```

### 5.5 `human_reviews`

One row per review action. Captures both gatekeeping decisions AND calibration overrides. This is the audit log AND the training dataset.

```
human_reviews
- id                       uuid, primary key
- article_id               uuid, FK → articles.id
- reviewer                 text, owner identifier
- mode                     text, enum: 'safety_gate' | 'calibration' | 'both'
- decision                 text, enum: 'approved' | 'rejected' | 'no_change'
- check_results            jsonb, e.g. {factual: true, on_topic: true, 
                                        source_link: true, not_duplicate: false}
- score_importance_human   smallint, nullable, the override
- score_urgency_human      smallint, nullable
- score_interest_human     smallint, nullable
- calibration_note         text, nullable, "why I disagreed with the AI"
- reviewed_at              timestamptz
```

Nullable score fields mean: in a rushed safety-gate-only review, leave them empty. When time permits, fill them in. Either way the article ships.

### 5.6 `processing_log`

Token and cost telemetry. Critical for staying under budget.

```
processing_log
- id              uuid, primary key
- call_type       text, enum: 'article_processor' | 'translation_hi'
                            | 'translation_mr' | 'newsletter'
- topic           text, nullable
- input_tokens    integer
- output_tokens   integer
- cache_read      integer, prompt-cache hit tokens (for tracking caching benefit)
- estimated_cost  numeric(10,4)
- duration_ms     integer
- success         boolean
- error_message   text, nullable
- called_at       timestamptz
```

---

## 6. Prompts

Three prompts in Phase 2/3. The newsletter prompt is preserved from `newsletter.py` and refactored to read from `approved_articles` instead of raw Tavily output.

### 6.1 Article processor (per-topic batch)

Called 6 times per daily run, once per topic. The input includes both the new batch (indexed) and recent headlines for dedup judgment.

```
You are a news editor for DING News, an AI-augmented news service. You 
receive a batch of raw article excerpts from a single news topic and 
produce one clean, factual JSON object per distinct news event.

The topic of this batch is "{topic}".

For each distinct news event in the input list, produce a JSON object 
with these fields:

- "source_indices": array of integers identifying which input articles 
  this summary draws from (0-indexed, in the order provided below). If 
  you merge multiple input articles into one event, list all their 
  indices. Every index must correspond to an article in the input list.
- "title": rewrite the original headline to be informative and neutral. 
  No clickbait, no emotional adjectives. Maximum 12 words.
- "balanced_summary": 100-120 words covering what happened, who was 
  involved, when and where, and the most important factual context. 
  Use only information from the source excerpts. If excerpts are too 
  thin to write a confident 100-word summary, write 60-90 words instead 
  — never invent details to hit a length target.
- "why_it_matters": 1-2 sentences explaining why a reader should care. 
  Focus on concrete consequences (economic, political, scientific). 
  Do not editorialize about whether the consequences are good or bad.
- "score": an object with three integer fields, each scored 1-5:
    - "importance": how consequential for the world or affected region?
    - "urgency": how time-sensitive is reading this today vs next week?
    - "reader_interest": how engaging to a general educated reader?
  
  Score "reader_interest" *relative to other articles in this batch*. 
  Within Sports, a championship final is a 5; within Business, a major 
  earnings miss might be a 5. You are scoring within-topic interest, 
  not cross-topic comparability.

- "ai_confidence": an object with three integer fields, each scored 1-5, 
  rating YOUR OWN confidence in this article:
    - "factual": confidence that every fact you included is verifiable 
      in the source excerpts (5 = no inferences, all facts directly 
      stated; 1 = significant inference required)
    - "on_topic": confidence that the summary stays on the actual story 
      without drifting to adjacent topics (5 = single tight focus)
    - "source_valid": confidence that the source URLs are correct and 
      will lead to the article they claim (5 = URLs are clean and from 
      reputable domains)
  
  Be honest. Articles with confidence 5 across all three may bypass 
  human review; articles with any field below 5 will be reviewed. Over-
  rating yourself produces published mistakes.

- "relationship_to_recent": one of:
    - "new": substantively new event, not covered in recent headlines
    - "followup": continues a recent story with meaningful new development
    - "duplicate": same event and same core development as a recent 
      headline; this should NOT be published. Return this rather than 
      skipping the article — we want to log what you considered a dup.

Hard rules:
- If a fact is not in the source excerpt, do not include it. No 
  invented numbers, names, quotes, or dates.
- Write in plain English at roughly an 8th-grade reading level.
- Return a JSON array. No prose outside the JSON. No markdown fences.
- If the input batch contains no genuinely newsworthy events, return [].

Input articles for topic "{topic}":
{indexed_articles}

Recent headlines (last 7 days; use to judge relationship_to_recent):
{recent_headlines}
```

Where `{indexed_articles}` is formatted as:
```
[0] Reuters: "OpenAI delays GPT-5 to December" (2026-05-11)
    Article snippet text here...
[1] AP: "OpenAI pushes GPT-5 launch back" (2026-05-11)
    Article snippet text here...
[2] Bloomberg: "Altman: GPT-5 in December" (2026-05-12)
    Article snippet text here...
```

Notes:
- `source_indices` lets Python derive `source_urls` and `tavily_ids` from the input batch it already has. Sonnet never restates URLs (Rule 3.1 + 3.5).
- `ai_confidence` enables auto-approval (Decision F). Sonnet is the worst judge of its own work in general, but for clearly-sourced wire stories it's reliable enough that 5-5-5 confidence is a useful default-publish signal in a beta.
- `relationship_to_recent` formalizes the dedup judgment that the current `newsletter.py` does implicitly via "DO NOT duplicate" instruction.

### 6.2 Hindi translation (per approved article)

Called per article after approval. Phase 3.

```
You are translating an English news article into Hindi for DING News. 
The reader is an educated Indian who reads news in Hindi but lives 
bilingually with English — comfortable with English loanwords where 
they are the natural choice.

Translate these fields from English to Hindi, preserving:
- Factual accuracy: every name, number, date, place stays exactly correct
- Political and cultural neutrality: do not introduce political 
  descriptors that weren't in the English version
- Tone: informative and calm, not sensational

Output a JSON object with the same field names but Hindi values:
- "title"
- "balanced_summary"
- "why_it_matters"

Style:
- Devanagari script. Proper nouns (Tesla, ChatGPT, Goldman Sachs, S&P 500, 
  NASA) stay in Roman script.
- Prefer everyday conversational Hindi over heavy Sanskrit-derived 
  vocabulary. The reader should not need a dictionary.
- Avoid forced replacements: if "computer", "smartphone", or "internet" 
  is the natural word a Hindi speaker would use, use it — do not 
  substitute "संगणक" or "अंतरजाल".
- Numbers stay as Arabic numerals (123, not १२३).
- Do not add explanations, context, or footnotes that weren't in the 
  English source.

Input:
{approved_article_json}
```

### 6.3 Newsletter generator (refactored)

Preserved from the current `newsletter.py` prompt (lines 171-264), with one change: the input `news_context` is now built from `approved_articles WHERE article_date = today ORDER BY rank_score DESC`, not from raw Tavily output. The existing HTML template stays.

Effective benefit: the newsletter now ships only reviewed articles (human or auto-approved), scored and ranked by an explicit metric.

### 6.4 Marathi translation

Deferred to Phase 5. Will mirror the Hindi prompt with Marathi-specific orthography rules. Reviewer identified (family member in Maharashtra). Not drafted in this document.

---

## 7. Decisions log

Explicit choices made during Day 2 design, with reasoning. Revisit if assumptions change.

### Decision A — `approved_articles` is a copy, not a reference

`approved_articles` duplicates content fields from `articles` rather than holding only a foreign key. Rationale: the published version should be immutable; fixing a typo in `articles` later should not change what readers saw yesterday. The table doubles as the daily archive — querying it requires no joins. Duplication cost is trivial at beta scale.

### Decision B — Hindi in Phase 3, Marathi in Phase 5

Original roadmap had perspectives in Phase 2 and translations in Phase 4. Reordered: family audience reads Hindi/Marathi and doesn't need US-style political framings. Translation is what makes the product useful to them. Marathi defers to Phase 5 because Hindi is the higher-volume initial use case.

### Decision C — Per-topic batching for article processing

Six Sonnet calls per day, one per topic, each returning a JSON array. Not per-article (system prompt amortization is bad). Not one mega-call (loses topic-relative scoring and failure isolation). Cost: ~$4.50/month with prompt caching enabled.

### Decision D — CLI review tool in Phase 2

Python CLI for v1, not a web UI. ~80 lines vs ~1 week. Defer web UI to Phase 5+ if CLI proves limiting.

### Decision E — Prompt caching enabled from day one

All Sonnet calls use `cache_control` on the system prompt. Reduces input cost ~80% on cached portion across 6 daily article-processor calls.

### Decision F — Auto-approve high-confidence articles

*[Added Day 2 evening]*

Articles where Sonnet's self-rated `ai_confidence` is 5 across all three dimensions (factual, on_topic, source_valid) bypass human review and publish automatically. Articles with any sub-5 confidence wait for human review.

Rationale: human bandwidth is the binding constraint, not AI cost. For well-sourced wire stories (Reuters, AP, Bloomberg) on factual events, AI self-confidence is a useful approximate signal. False positives are an acceptable beta risk — every auto-approved article is still spot-checkable post-publish via calibration mode.

Tradeoff accepted: some bad articles will ship. Mitigation: every auto-approved article is visible in the CLI tool, and weekly catch-up review surfaces them for retroactive calibration. The data flows into Rule 3.4 training material.

This decision is reversible: if auto-approval quality is poor, raise the bar (require importance >= 4 in addition to confidence 5-5-5), or revert to all-pending until you have catch-up bandwidth.

### Decision G — Dedup is URL exact match + Sonnet-judged title similarity

*[Added Day 2 evening]*

Two layers:
1. **Python pre-filter**: drop articles whose URL exactly matches any URL published in the last 7 days. Trivially handled before any AI cost is incurred.
2. **Sonnet judgment**: the article processor receives recent headlines as context and returns `relationship_to_recent` ∈ {new, followup, duplicate}. Articles judged "duplicate" are stored with `status='auto_rejected'` (for telemetry) but never displayed. Follow-ups publish normally.

Human review Q5 ("Different from articles published in last 3 days?") catches what Sonnet missed.

Rationale: evolving stories (war, court cases) should publish — a war update on day 12 is news. Re-warmed coverage of the same development should not. The "relationship_to_recent" judgment is fuzzy enough that Sonnet should make the first call, with human review as the final filter.

### Decision H — Cross-topic ranking: importance × 2 + urgency + interest

*[Added Day 2 evening]*

Composite `rank_score` for cross-topic feed ordering. Importance weighted 2x because it's the most cross-topic-comparable signal (a major war beats a routine earnings call regardless of how interesting the earnings are within Business).

Within-topic ranking (just `reader_interest`) remains available via the column. Future curated-topic feeds ("all Business this week") can use within-topic scoring directly without computing the composite.

Validate empirically on first 50 approved articles. If the formula consistently surfaces wrong things, recompute with different weights — backfilling `rank_score` is a single SQL UPDATE.

---

## 8. Human review

### 8.1 Two modes, two purposes

Review serves two distinct jobs that should not be conflated:

- **Safety gate (mandatory for `pending` articles)**: fast yes/no on whether the article is safe to publish. ~20 seconds per article. Blocks bad output from reaching readers.
- **Calibration (optional, valuable always)**: capture better scores than the AI gave, plus a short note on why. Becomes training data per Rule 3.4. Runs over `auto_approved` articles too — they shipped without review, but calibration improves the system.

These are two CLI subcommands. Implementation: `python review_today.py` runs safety gate over pending; `python calibrate.py [--days N]` runs calibration over any approved article from the last N days.

### 8.2 Safety gate checklist

Five questions per article. Blocking questions auto-reject on No.

| # | Question | Blocking? |
|---|---|---|
| 1 | Are all facts (names, numbers, dates, quotes) verifiable in the source excerpt? | Yes |
| 2 | Did the summary stay on the actual story, or drift to adjacent topics? | Yes |
| 3 | Does the source URL open the article it claims to be from? | Yes |
| 4 | Is this meaningfully different from articles published in the last 3 days? | Yes |
| 5 | Does the AI's importance/urgency score roughly match my gut? | No (calibration only) |

For translations (Phase 3+), one additional blocking question:
| 6 | (Hindi/Marathi) Does the translation preserve meaning and tone, or flatten nuance? | Yes |

Question 4 was non-blocking in the prior draft and is now blocking — duplicate-warmed news is the most common quality problem in AI news systems and warrants a hard stop.

### 8.3 Calibration mode

For each article being calibrated:
- Show the AI's scores (importance, urgency, reader_interest)
- Prompt for human overrides (any subset; skip means "AI was right")
- Prompt for a short calibration note (free text, optional)
- Write to `human_reviews` with `mode='calibration'`

The note matters more than the numbers. "AI rated importance 4 but the company is a major regional employer that wire services underplay" is a pattern worth capturing.

### 8.4 Missed-day handling

What happens when the human disappears for a stretch (Yellowstone, Tesla emergency, life):

- **Default behavior**: the daily pipeline runs. URL-deduped articles process through Sonnet. Auto-approved articles (confidence 5-5-5, non-duplicate) publish to `approved_articles` and feed both newsletter and PWA. Pending articles accumulate quietly.
- **Catch-up review** (when bandwidth returns): `python review_today.py --catch-up` shows pending articles from prior days. Auto-approved articles can be retroactively flagged in calibration mode but are not unpublished.
- **Newsletter on missed days**: still sends, but only includes auto-approved articles. If on any given day there are <3 auto-approved articles, the script skips that day's send and posts a "light news day" admin note.

This is the honest tradeoff: the system runs autonomously when the human is absent, which means some bad articles will ship. For a beta with family readers and public-news content, this risk is acceptable. It would not be for a financial trading newsletter.

---

## 9. Cost model

Beta-scale estimate (5-10 articles approved per day after review/auto-approval):

| Component | Calls/day | Est. cost/month |
|---|---|---|
| Article processor (per-topic batch, w/ caching) | 6 | $4.50 |
| Hindi translation (per approved article) | ~10 | $2.25 |
| Newsletter generator (refactored) | 1 | $1.00 |
| Supabase (free tier) | — | $0.00 |
| Vercel hosting (free tier) | — | $0.00 |
| Domain (subdomain of sanchitagarwal.com) | — | $0.00 |
| **Total** | | **~$8/month** |

All costs scale linearly with article volume. If cost exceeds $20/month unexpectedly, reduce daily article volume before investigating other causes.

Adding `ai_confidence` and `relationship_to_recent` to the prompt output increases output tokens by ~30 per article. Negligible cost impact (~$0.05/month). Worth it.

---

## 10. Open questions

To resolve before or during Phase 2.

- [ ] **Tavily field verification.** Confirm Tavily returns `tavily_id` (or equivalent), `published_date`, and `url` for every result. Audit on Day 1 of Phase 2 before writing migration code. Applies to all fields the new schema sources from Tavily.
- [ ] **Beta tester list.** Sudeep, Vaishnavi, plus 3-5 family members for Hindi review. Specific names committed before Phase 4.

Closed during Day 2 evening: cross-topic ranking (Decision H), dedup strategy (Decision G), missed-day handling (Section 8.4). Deferred: backup strategy (not concerned at beta scale).

---

## 11. Phase 2 task list

Concrete next-step work. Each item ends with a commit.

- [ ] **2.0** Verify Tavily returns all needed fields (`tavily_id`, `published_date`, `url`); patch fetcher if not
- [ ] **2.1** Set up Supabase project; run schema migrations for all 6 tables
- [ ] **2.2** Refactor `newsletter.py` to write fetched articles to `articles` table (status='pending'), preserving existing newsletter as downstream consumer
- [ ] **2.3** Implement URL-based Python pre-filter against last 7 days
- [ ] **2.4** Implement the article processor: 6 Sonnet calls per run with the per-topic prompt; populate balanced_summary, why_it_matters, scores, ai_confidence, relationship_to_recent
- [ ] **2.5** Implement Python orchestration that uses `source_indices` to derive `source_urls` and `tavily_ids` from the input batch
- [ ] **2.6** Implement auto-approval routing (confidence 5-5-5 + non-duplicate → `approved_articles`)
- [ ] **2.7** Add `processing_log` writes around every Sonnet call, including cache_read tokens
- [ ] **2.8** Build the CLI safety-gate tool (`review_today.py`) with the 5-question checklist; supports `--catch-up`
- [ ] **2.9** Build the CLI calibration tool (`calibrate.py`) for score overrides + notes
- [ ] **2.10** End-to-end test: fetch → process → review 5 articles → confirm they land in `approved_articles`; auto-approve 2 articles separately and verify they also land
- [ ] **2.11** Refactor newsletter generator to read from `approved_articles` ORDER BY rank_score
- [ ] **2.12** Verify next-morning newsletter still sends correctly to subscribers
- [ ] **2.13** Commit Phase 2 retrospective; update Decisions Log with anything that changed during implementation

Phase 2 done gate: a daily newsletter is sent that contains *only* reviewed articles (human or auto-approved), scored and ranked by `rank_score`, with full token telemetry visible in `processing_log` and human calibration data accumulating in `human_reviews`.

---

*End of design document. Update Decisions Log as choices evolve. Add new Open Questions as they arise. Re-read Design Rules when in doubt.*
