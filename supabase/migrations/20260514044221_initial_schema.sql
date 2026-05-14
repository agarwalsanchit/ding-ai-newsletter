-- =============================================================================
-- DING News — initial schema
-- DESIGN.md §5.1–5.6
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 5.1  sources
-- Static config table: one row per Tavily topic. Rarely changes at runtime.
-- RESTRICT on delete: you should never silently lose a topic config that
-- articles still point to. Explicitly remove articles first.
-- ---------------------------------------------------------------------------
CREATE TABLE sources (
    source_url    text        PRIMARY KEY,  -- Tavily query string; unique identifier (topic names may collide)
    topic         text        NOT NULL,
    tavily_query  text        NOT NULL,
    -- Optional allowlist of domains passed to Tavily (e.g. '{reuters.com,apnews.com}').
    -- NULL means no domain filter.
    domain_filter text[],
    active        boolean     NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 5.2  articles
-- Full draft pool: every AI-processed article, including rejections.
-- This is the source of truth for what Claude produced; nothing is deleted.
-- RESTRICT from sources: if a topic config is removed the orphaned drafts
-- have no meaning — require explicit cleanup rather than silent cascade.
-- ---------------------------------------------------------------------------
CREATE TABLE articles (
    id                     uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    source_url             text        NOT NULL REFERENCES sources(source_url) ON DELETE RESTRICT,

    -- Python-derived, never written by Claude (DESIGN.md Rule 3.1 + 3.5).
    -- Arrays because one AI article may merge multiple Tavily inputs.
    source_urls            text[]      NOT NULL DEFAULT '{}',

    -- Tavily returns no stable per-article ID; URL is the dedup key.
    -- Kept as a separate column in case Tavily adds IDs later.
    tavily_ids             text[]      NOT NULL DEFAULT '{}',

    -- Copied from sources.topic at insert time so queries never need a join
    -- just to filter by topic.
    topic                  text        NOT NULL,

    -- From Tavily's published_date — NOT from Claude.
    article_date           date        NOT NULL,

    -- Claude-generated fields
    title                  text,
    balanced_summary       text,
    why_it_matters         text,

    -- Scores 1-5; nullable until Claude processes the row.
    score_importance       smallint    CHECK (score_importance       BETWEEN 1 AND 5),
    score_urgency          smallint    CHECK (score_urgency          BETWEEN 1 AND 5),
    score_interest         smallint    CHECK (score_interest         BETWEEN 1 AND 5),

    -- Claude's self-rated confidence (DESIGN.md §6.1). All three must be 5
    -- for auto-approval (Decision F).
    ai_confidence_factual  smallint    CHECK (ai_confidence_factual  BETWEEN 1 AND 5),
    ai_confidence_on_topic smallint    CHECK (ai_confidence_on_topic BETWEEN 1 AND 5),
    ai_confidence_source   smallint    CHECK (ai_confidence_source   BETWEEN 1 AND 5),

    relationship_to_recent text        CHECK (relationship_to_recent IN ('new', 'followup', 'duplicate')),

    -- Five-value lifecycle enum:
    --   pending       → awaits human safety-gate review
    --   approved      → human approved
    --   auto_approved → confidence 5-5-5 + non-duplicate; bypassed human review
    --   rejected      → human rejected
    --   auto_rejected → Claude flagged as duplicate; stored for telemetry only
    status                 text        NOT NULL DEFAULT 'pending'
                                       CHECK (status IN ('pending', 'approved', 'auto_approved',
                                                         'rejected', 'auto_rejected')),

    fetched_at             timestamptz NOT NULL DEFAULT now(),
    processed_at           timestamptz,
    reviewed_at            timestamptz  -- NULL until human or auto-approval occurs
);

CREATE INDEX articles_status_idx       ON articles (status);
CREATE INDEX articles_topic_idx        ON articles (topic);
CREATE INDEX articles_article_date_idx ON articles (article_date);

-- ---------------------------------------------------------------------------
-- 5.3  approved_articles
-- Immutable publish record: a copy of fields from articles, not a reference.
-- (Decision A: the published version must not change if the draft is edited.)
-- CASCADE from articles: if a draft is somehow deleted, its published copy
-- loses meaning and should go with it.
-- ---------------------------------------------------------------------------
CREATE TABLE approved_articles (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id       uuid        NOT NULL REFERENCES articles(id) ON DELETE CASCADE,

    topic            text        NOT NULL,
    article_date     date        NOT NULL,
    title            text        NOT NULL,
    balanced_summary text        NOT NULL,
    why_it_matters   text        NOT NULL,

    score_importance smallint    NOT NULL CHECK (score_importance BETWEEN 1 AND 5),
    score_urgency    smallint    NOT NULL CHECK (score_urgency    BETWEEN 1 AND 5),
    score_interest   smallint    NOT NULL CHECK (score_interest   BETWEEN 1 AND 5),

    -- Computed at insert: importance×2 + urgency + interest (Decision H).
    -- Stored, not computed at query time, so a formula change is one UPDATE.
    rank_score       numeric     NOT NULL,

    source_urls      text[]      NOT NULL DEFAULT '{}',

    approved_at      timestamptz NOT NULL DEFAULT now(),
    approved_by      text        NOT NULL CHECK (approved_by IN ('human', 'ai_auto')),

    -- NULL until the newsletter/PWA consumer marks it published.
    published_at     timestamptz,

    -- Redundant with article_date but denormalised for fast daily archive
    -- queries (SELECT * FROM approved_articles WHERE archived_for_date = $1).
    archived_for_date date       NOT NULL
);

CREATE INDEX approved_articles_article_date_idx      ON approved_articles (article_date);
CREATE INDEX approved_articles_rank_score_idx        ON approved_articles (rank_score DESC);
CREATE INDEX approved_articles_archived_for_date_idx ON approved_articles (archived_for_date);

-- ---------------------------------------------------------------------------
-- 5.4  translations
-- One row per (approved_article × language). Single table; adding a language
-- requires no schema change, only a new CHECK value (or drop the CHECK).
-- CASCADE: if the approved article is removed, its translations are meaningless.
-- UNIQUE constraint enforces one translation per article per language.
-- ---------------------------------------------------------------------------
CREATE TABLE translations (
    id                        uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    approved_article_id       uuid        NOT NULL REFERENCES approved_articles(id) ON DELETE CASCADE,
    language                  text        NOT NULL CHECK (language IN ('hi', 'mr')),
    title_translated          text,
    summary_translated        text,
    why_it_matters_translated text,
    translated_at             timestamptz NOT NULL DEFAULT now(),
    reviewed                  boolean     NOT NULL DEFAULT false,
    reviewer_notes            text,

    UNIQUE (approved_article_id, language)
);

-- Covering index for the common lookup: "give me the Hindi translation for
-- this article". The UNIQUE constraint creates an index too, but an explicit
-- named one is easier to reference in EXPLAIN output.
CREATE INDEX translations_article_language_idx ON translations (approved_article_id, language);

-- ---------------------------------------------------------------------------
-- 5.5  human_reviews
-- Audit log AND training dataset (DESIGN.md Rule 3.4).
-- One row per review action; multiple rows per article are normal
-- (safety gate on day 1, calibration override on day 3).
-- RESTRICT: never silently delete review history if the article is removed.
-- ---------------------------------------------------------------------------
CREATE TABLE human_reviews (
    id                     uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id             uuid        NOT NULL REFERENCES articles(id) ON DELETE RESTRICT,
    reviewer               text        NOT NULL,
    mode                   text        NOT NULL CHECK (mode IN ('safety_gate', 'calibration', 'both')),
    decision               text        NOT NULL CHECK (decision IN ('approved', 'rejected', 'no_change')),

    -- Structured checklist results stored as JSONB so the schema doesn't need
    -- to change when checklist questions are added/removed.
    -- Example: {"factual": true, "on_topic": true, "source_link": true, "not_duplicate": false}
    check_results          jsonb,

    -- Nullable: only populated during calibration mode (DESIGN.md §8.3).
    -- NULL means "AI score was acceptable, no override needed."
    score_importance_human smallint    CHECK (score_importance_human BETWEEN 1 AND 5),
    score_urgency_human    smallint    CHECK (score_urgency_human    BETWEEN 1 AND 5),
    score_interest_human   smallint    CHECK (score_interest_human   BETWEEN 1 AND 5),

    calibration_note       text,
    reviewed_at            timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX human_reviews_article_id_idx ON human_reviews (article_id);

-- ---------------------------------------------------------------------------
-- 5.6  processing_log
-- Token and cost telemetry for every Claude API call (DESIGN.md §5.6).
-- No foreign keys: log rows are append-only telemetry; they should survive
-- even if referenced articles are cleaned up.
-- ---------------------------------------------------------------------------
CREATE TABLE processing_log (
    id             uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    call_type      text          NOT NULL CHECK (call_type IN (
                                     'article_processor',
                                     'translation_hi',
                                     'translation_mr',
                                     'newsletter'
                                 )),
    topic          text,         -- NULL for newsletter and translation calls
    input_tokens   integer       NOT NULL DEFAULT 0,
    output_tokens  integer       NOT NULL DEFAULT 0,
    -- Prompt-cache hit tokens tracked separately to measure caching benefit
    -- (Decision E: caching enabled from day one).
    cache_read     integer       NOT NULL DEFAULT 0,
    estimated_cost numeric(10,4) NOT NULL DEFAULT 0,
    duration_ms    integer,
    success        boolean       NOT NULL DEFAULT true,
    error_message  text,
    called_at      timestamptz   NOT NULL DEFAULT now()
);
