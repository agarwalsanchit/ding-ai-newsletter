"""
DING.AI Pipeline Engine — DESIGN.md tasks 2.4–2.7b
Runs after news fetch to AI-process articles and generate the daily brief.

Entry point: python pipeline.py

Environment variables (same as newsletter.py):
  ANTHROPIC_API_KEY  — from platform.anthropic.com
  TAVILY_API_KEY     — from app.tavily.com
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY — from supabase.env
"""

import anthropic
import json
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from dotenv import load_dotenv
from supabase import create_client
from tavily import TavilyClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

load_dotenv("supabase.env")  # SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
load_dotenv()                # .env — ANTHROPIC_API_KEY, TAVILY_API_KEY

# ── Config ────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
TAVILY_API_KEY    = os.environ.get("TAVILY_API_KEY")
SUPABASE_URL      = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY      = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

HISTORY_FILE = "history/newsletter_history.json"

SECTIONS = [
    ("🌍 Geopolitics & World Affairs", "geopolitics international conflict diplomacy world news today"),
    ("💼 Business & Finance",          "stock market economy business earnings finance news today"),
    ("🔬 Science & Technology",        "AI artificial intelligence science technology innovation research news today"),
    ("🎾 Sports & Entertainment",      "Premier League La Liga IPL cricket NFL F1 tennis Grand Slam sports news results today site:apnews.com OR site:reuters.com OR site:bbc.com OR site:espn.com/story"),
    ("🏛 Society & Culture",           "society culture politics social trends education news today"),
]

# URL patterns that produce video/podcast pages with no summarisable text
BLOCKED_URL_PATTERNS = [
    "/videos/",
    "/video/",
    "/podcast/",
    "/live-blog/",
    "/watch/player/",           # ESPN video embeds
    "/watch/soccer/",           # CBS Sports soccer video
    "/watch/",                  # Generic watch/stream pages
    "boxscore",                 # Fox Sports / ESPN boxscore pages (no article text)
    "game-boxscore",
    "live-score",
    "live_score",
    "newsworthy-for-",          # WFAE newsworthy podcast
    "the-bulletin-may",         # Newsweek daily video bulletins
    "photo-gallery",            # AP photo galleries
    "/espn/story/",             # ESPN live sport blogs (score-only)
]

# Claude Sonnet 4.6 pricing (per million tokens)
PRICE_INPUT       = 3.00 / 1_000_000
PRICE_OUTPUT      = 15.00 / 1_000_000
PRICE_CACHE_READ  = 0.30 / 1_000_000

# ── System prompts ────────────────────────────────────────────────────────────
ARTICLE_PROCESSOR_SYSTEM = """You are the article processor for DING News, a daily AI-curated briefing for readers who want signal over noise.

Given raw news snippets for a single topic, identify distinct news events and return structured summaries for each one.

Rules:
- Reference input articles ONLY by their 0-based index (source_indices). Never restate content; indices are validated by the pipeline.
- Merge multiple input articles that cover the same event into one output object.
- Do NOT invent facts not present in the input articles.
- article_brief: 40–60 words. Card-face brief — the first thing a reader sees. Key facts only: who/what/when/where. No "why it matters," no background context. First sentence carries the most important fact. Must fit one mobile screen without truncation.
- balanced_summary: 100–120 words, card-facing, factual and balanced. A reader should understand the event in 30 seconds.
- detail_summary: 300–400 words, detail-view-facing. Same tone and source-grounding as balanced_summary but more depth: additional named entities, concrete numbers, background context. Do NOT add claims not in the sources.
- why_it_matters: 1–2 sentences on the real-world consequence. Specific, not generic.
- score_importance (1–5): global significance.
- score_urgency (1–5): time-sensitivity (5 = must read today; 1 = evergreen).
- score_interest (1–5): interest for a general educated reader. For sports: score high (4–5) for global or mass-viewership events (football/soccer, cricket/IPL, Olympics, F1, tennis Grand Slams, NFL); score low (1–2) for regional or niche sports (lacrosse, curling, local leagues).
- ai_confidence_factual (1–5): confidence all stated facts are accurate.
- ai_confidence_on_topic (1–5): confidence it is genuinely about the topic.
- ai_confidence_source (1–5): source credibility (5 = AP/Reuters/BBC; 1 = unknown blog).
- relationship_to_recent: classify against the recent coverage list.
  "new" — the core event or topic has not appeared in recent coverage.
  "followup" — the same underlying story appeared before, BUT there is a materially new fact that changes the picture: a number changed, a decision was made, a new actor entered, an outcome was announced, a timeline shifted. More reporting on the same situation without new facts does NOT qualify as "followup" — it is "duplicate".
  "duplicate" — the same story was already covered and today's articles add no new information a reader hasn't already seen. Be strict: when uncertain between "followup" and "duplicate", choose "duplicate".
- Return a JSON array only. No markdown fences. No prose outside the JSON."""

BRIEF_GENERATOR_SYSTEM = "You are the editor of DING News, a daily AI-curated briefing."

# ── Retry helper ──────────────────────────────────────────────────────────────
def with_retry(fn, max_attempts: int = 3, base_delay: float = 4.0):
    """Call fn(); on exception, retry with exponential backoff."""
    last_err = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if attempt < max_attempts - 1:
                wait = base_delay * (2 ** attempt)
                logging.warning("Attempt %d failed: %s. Retrying in %.0fs…", attempt + 1, e, wait)
                time.sleep(wait)
    raise last_err


# ── History helpers ───────────────────────────────────────────────────────────
def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def get_recent_headlines(history):
    cutoff  = (date.today() - timedelta(days=7)).isoformat()
    recent  = [e for e in history if e.get("date", "") >= cutoff]
    headlines = []
    for entry in recent:
        headlines.extend(entry.get("headlines", []))
    return headlines


def get_recent_approved_context(db) -> list:
    """Return rich recent-coverage strings from approved_articles (last 7 days).

    These are authoritative — they're stories we have already published or
    approved. Used by Claude to detect genuine duplicates vs. real follow-ups.
    Format: "[YYYY-MM-DD / topic] Title" so Claude can judge recency and topic.
    """
    cutoff = (date.today() - timedelta(days=7)).isoformat()
    try:
        result = (
            db.table("approved_articles")
            .select("title, topic, article_date")
            .gte("article_date", cutoff)
            .order("article_date", desc=True)
            .execute()
        )
        lines = []
        for r in result.data:
            if r.get("title"):
                lines.append(f"[{r['article_date']} / {r['topic']}] {r['title']}")
        return lines
    except Exception as exc:
        logging.warning("Could not fetch recent approved context: %s", exc)
        return []


# ── News fetching ─────────────────────────────────────────────────────────────
def search_news(tavily: TavilyClient, query: str, max_results: int = 10) -> list:
    def _search():
        return tavily.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
            include_raw_content=False,
            days=2,
            topic="news",
        ).get("results", [])
    try:
        return with_retry(_search)
    except Exception as e:
        logging.warning("Tavily search failed for '%s': %s", query, e)
        return []


# ── Supabase persistence ──────────────────────────────────────────────────────
def persist_fetched_articles(db, articles_by_section: dict) -> dict:
    """Insert pending article rows; return {topic: {url: article_id}} mapping.

    Differs from newsletter.py's version: takes an existing db client and
    returns a topic→url→id dict instead of a flat list of IDs, so the pipeline
    can look up IDs when writing Claude output back to the articles table.
    """
    # Build URL dedup set from last 7 days
    cutoff = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    try:
        existing = db.table("articles").select("source_urls").gte("fetched_at", cutoff).execute()
        seen_urls: set = set()
        for row in existing.data:
            for url in (row.get("source_urls") or []):
                seen_urls.add(url)
        logging.info("Dedup set: %d URLs seen in last 7 days.", len(seen_urls))
    except Exception as exc:
        logging.error("Failed to fetch existing URLs for dedup: %s — skipping dedup.", exc)
        seen_urls = set()

    # Cache source_id lookups
    source_id_cache: dict = {}

    def get_source_id(topic: str):
        if topic in source_id_cache:
            return source_id_cache[topic]
        try:
            result = db.table("sources").select("id").eq("topic", topic).execute()
            if result.data:
                source_id_cache[topic] = result.data[0]["id"]
                return source_id_cache[topic]
            logging.warning("No sources row found for topic %r — skipping.", topic)
            return None
        except Exception as exc:
            logging.error("Failed to look up source_id for topic %r: %s", topic, exc)
            return None

    # {topic: {url: article_id}}
    mapping: dict = {}
    total = deduped = errors = 0

    for topic, articles in articles_by_section.items():
        source_id = get_source_id(topic)
        mapping[topic] = {}

        for article in articles:
            total += 1
            url = article.get("url", "")

            if article.get("score", 1.0) < 0.4:
                logging.info("  SKIP (low score %.2f): %s", article.get("score", 0), url)
                deduped += 1
                continue

            if any(pat in url for pat in BLOCKED_URL_PATTERNS):
                logging.info("  SKIP (blocked pattern): %s", url[:80])
                deduped += 1
                continue

            if url in seen_urls:
                logging.info("  SKIP (dedup): %s", url)
                deduped += 1
                continue

            raw_date = article.get("published_date", "")
            try:
                article_date = parsedate_to_datetime(raw_date).date().isoformat()
            except Exception:
                article_date = date.today().isoformat()
                logging.warning("  Could not parse date %r for %s — using today.", raw_date, url)

            if source_id is None:
                logging.warning("  SKIP (no source_id): %s", url)
                errors += 1
                continue

            row = {
                "source_id":    source_id,
                "source_urls":  [url],
                "topic":        topic,
                "article_date": article_date,
                "status":       "pending",
            }

            try:
                result = db.table("articles").insert(row).execute()
                new_id = result.data[0]["id"]
                mapping[topic][url] = new_id
                seen_urls.add(url)
                logging.info("  INSERT %s → %s", url[:80], new_id)
            except Exception as exc:
                logging.error("  FAIL inserting %s: %s", url, exc)
                errors += 1

    logging.info(
        "persist_fetched_articles: %d total | %d inserted | %d deduped | %d errors",
        total,
        sum(len(v) for v in mapping.values()),
        deduped,
        errors,
    )
    return mapping


# ── Processing log helper ─────────────────────────────────────────────────────
def log_call(db, call_type: str, topic, response, duration_ms: int,
             success: bool, error_message=None):
    """Write a row to processing_log."""
    usage = getattr(response, "usage", None) if response else None
    input_tokens  = getattr(usage, "input_tokens", 0) if usage else 0
    output_tokens = getattr(usage, "output_tokens", 0) if usage else 0
    cache_read    = getattr(usage, "cache_read_input_tokens", 0) if usage else 0

    estimated_cost = (
        input_tokens  * PRICE_INPUT +
        output_tokens * PRICE_OUTPUT +
        cache_read    * PRICE_CACHE_READ
    )

    row = {
        "call_type":      call_type,
        "topic":          topic,
        "input_tokens":   input_tokens,
        "output_tokens":  output_tokens,
        "cache_read":     cache_read,
        "estimated_cost": float(round(estimated_cost, 6)),
        "duration_ms":    duration_ms,
        "success":        success,
        "error_message":  error_message,
    }
    try:
        db.table("processing_log").insert(row).execute()
    except Exception as exc:
        logging.error("Failed to insert processing_log row: %s", exc)


# ── Article processor ─────────────────────────────────────────────────────────
def build_article_user_message(topic: str, articles: list, recent_headlines: list) -> str:
    """Build the per-topic user message for article_processor."""
    indexed_articles = ""
    for i, a in enumerate(articles):
        title   = a.get("title", "Untitled")
        snippet = a.get("content", a.get("snippet", ""))[:600]
        url     = a.get("url", "")
        pub     = a.get("published_date", "recent")
        indexed_articles += (
            f"[{i}] Title: {title}\n"
            f"    Published: {pub}\n"
            f"    URL: {url}\n"
            f"    Content: {snippet}\n\n"
        )

    recent_str = "\n".join(f"- {h}" for h in recent_headlines) if recent_headlines else "(none)"

    return f"""Topic: {topic}

## Input articles (0-indexed):
{indexed_articles.strip()}

## Recently covered stories (last 7 days — use for duplicate/followup detection):
Format: [date / section] Title
{recent_str}

Return a JSON array. Each element:
{{
  "source_indices": [0],
  "title": "...",
  "article_brief": "...",
  "balanced_summary": "...",
  "detail_summary": "...",
  "why_it_matters": "...",
  "score_importance": 4,
  "score_urgency": 3,
  "score_interest": 4,
  "ai_confidence_factual": 5,
  "ai_confidence_on_topic": 5,
  "ai_confidence_source": 4,
  "relationship_to_recent": "new"
}}"""


def process_topic(claude_client, db, topic: str, articles: list,
                  url_to_id: dict, recent_headlines: list) -> list:
    """Run article_processor for one topic. Returns list of processed article IDs."""
    if not articles:
        logging.info("  No articles for topic %r — skipping.", topic)
        return []

    user_message = build_article_user_message(topic, articles, recent_headlines)

    t0 = time.monotonic()
    response = None
    error_msg = None
    try:
        def _call():
            return claude_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=8192,
                system=[
                    {
                        "type": "text",
                        "text": ARTICLE_PROCESSOR_SYSTEM,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_message}],
            )

        response = with_retry(_call)
    except Exception as e:
        error_msg = str(e)
        logging.error("Claude call failed for topic %r: %s", topic, e)
    finally:
        duration_ms = int((time.monotonic() - t0) * 1000)
        log_call(
            db,
            call_type="article_processor",
            topic=topic,
            response=response,
            duration_ms=duration_ms,
            success=(response is not None),
            error_message=error_msg,
        )

    if response is None:
        return []

    raw = response.content[0].text.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw   = "\n".join(lines[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.split("\n")[:-1])
    raw = raw.strip()

    try:
        items = json.loads(raw)
        if not isinstance(items, list):
            raise ValueError("Expected JSON array")
    except Exception as e:
        logging.error("Failed to parse Claude response for topic %r: %s", topic, e)
        logging.debug("Raw response: %s", raw[:500])
        return []

    processed_ids = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for item in items:
        source_indices = item.get("source_indices", [])

        # DESIGN.md Rule 4.5: validate indices against actual input list length
        valid_indices = [i for i in source_indices if isinstance(i, int) and 0 <= i < len(articles)]
        if not valid_indices:
            logging.warning("  No valid source_indices in item %r — skipping.", item.get("title"))
            continue

        # Collect URLs for the merged article
        merged_urls = []
        for idx in valid_indices:
            url = articles[idx].get("url", "")
            if url:
                merged_urls.append(url)

        primary_idx = valid_indices[0]
        primary_url = articles[primary_idx].get("url", "")
        primary_id  = url_to_id.get(primary_url)

        if not primary_id:
            logging.warning(
                "  No article_id for primary URL %s (topic %r) — skipping.", primary_url, topic
            )
            continue

        relationship = item.get("relationship_to_recent", "new")
        conf_factual  = item.get("ai_confidence_factual", 1)
        conf_on_topic = item.get("ai_confidence_on_topic", 1)
        conf_source   = item.get("ai_confidence_source", 1)

        # Routing logic (DESIGN.md Decision F / Decision O)
        # Threshold: all three confidence axes >= 4 (confidence > 3).
        # 5/5/5 was too strict in practice — many accurate articles scored 4 on
        # one axis (e.g., sports factual confidence). Deck caps at 10 by rank_score.
        if relationship == "duplicate":
            status = "auto_rejected"
        elif conf_factual >= 4 and conf_on_topic >= 4 and conf_source >= 4:
            status = "auto_approved"
        else:
            status = "pending"

        # Build update payload for primary article
        update_payload = {
            "title":                  item.get("title"),
            "article_brief":          item.get("article_brief"),
            "balanced_summary":       item.get("balanced_summary"),
            "detail_summary":         item.get("detail_summary"),
            "why_it_matters":         item.get("why_it_matters"),
            "score_importance":       item.get("score_importance"),
            "score_urgency":          item.get("score_urgency"),
            "score_interest":         item.get("score_interest"),
            "ai_confidence_factual":  conf_factual,
            "ai_confidence_on_topic": conf_on_topic,
            "ai_confidence_source":   conf_source,
            "relationship_to_recent": relationship,
            "status":                 status,
            "processed_at":           now_iso,
            # Merge all source URLs from merged articles
            "source_urls":            merged_urls if len(merged_urls) > 1 else None,
        }
        # Remove None values to avoid overwriting existing source_urls
        update_payload = {k: v for k, v in update_payload.items() if v is not None}

        try:
            db.table("articles").update(update_payload).eq("id", primary_id).execute()
            logging.info("  Updated article %s (%s) → %s", primary_id[:8], topic, status)
            processed_ids.append(primary_id)
        except Exception as exc:
            logging.error("  Failed to update article %s: %s", primary_id, exc)
            continue

        # Auto-approve: insert into approved_articles
        if status == "auto_approved":
            # Fetch article_date from the DB row (was set at persist time)
            try:
                row_data = db.table("articles").select("article_date").eq("id", primary_id).execute()
                article_date_str = row_data.data[0]["article_date"] if row_data.data else date.today().isoformat()
            except Exception:
                article_date_str = date.today().isoformat()

            approved_row = {
                "article_id":      primary_id,
                "topic":           topic,
                "article_date":    article_date_str,
                "title":           item.get("title"),
                "article_brief":   item.get("article_brief"),
                "balanced_summary": item.get("balanced_summary"),
                "detail_summary":  item.get("detail_summary"),
                "why_it_matters":  item.get("why_it_matters"),
                "score_importance": item.get("score_importance"),
                "score_urgency":    item.get("score_urgency"),
                "score_interest":   item.get("score_interest"),
                "source_urls":      merged_urls,
                "approved_by":      "ai_auto",
            }
            try:
                db.table("approved_articles").insert(approved_row).execute()
                logging.info("  AUTO-APPROVED → approved_articles: %s", item.get("title", "")[:60])
            except Exception as exc:
                logging.error("  Failed to insert approved_articles for %s: %s", primary_id, exc)

        # Mark secondary (merged) articles as auto_rejected.
        # Do NOT set processed_at — DB check requires Claude fields when processed_at is set.
        # Status alone is enough to exclude them from the idempotency query below.
        for secondary_idx in valid_indices[1:]:
            secondary_url = articles[secondary_idx].get("url", "")
            secondary_id  = url_to_id.get(secondary_url)
            if not secondary_id:
                continue
            try:
                db.table("articles").update({
                    "status": "auto_rejected",
                }).eq("id", secondary_id).execute()
                logging.info("  Marked merged secondary %s as auto_rejected", secondary_id[:8])
            except Exception as exc:
                logging.error("  Failed to mark secondary %s: %s", secondary_id, exc)

    return processed_ids


# ── Top News flagging ─────────────────────────────────────────────────────────
def flag_top_news(db, today_str: str) -> None:
    """Find today's highest-importance+urgency article and label it 🚨 Top News.

    Runs after all topic sections are processed. The article keeps a record of
    its original section in the DB but both articles and approved_articles get
    their topic updated so the deck surfaces it at the top with the right chip.
    """
    try:
        result = (
            db.table("articles")
            .select("id, topic, title, score_importance, score_urgency, status")
            .eq("article_date", today_str)
            .in_("status", ["auto_approved", "approved"])
            .not_.is_("score_importance", "null")
            .execute()
        )
    except Exception as exc:
        logging.error("flag_top_news: failed to fetch articles: %s", exc)
        return

    if not result.data:
        logging.info("flag_top_news: no scored articles for %s.", today_str)
        return

    # Already flagged this run?
    if any(a["topic"] == "🚨 Top News" for a in result.data):
        logging.info("flag_top_news: top news already flagged for %s.", today_str)
        return

    top = max(
        result.data,
        key=lambda a: (a.get("score_importance") or 0) + (a.get("score_urgency") or 0),
    )

    try:
        db.table("articles").update({"topic": "🚨 Top News"}).eq("id", top["id"]).execute()
    except Exception as exc:
        logging.error("flag_top_news: failed to update articles: %s", exc)
        return

    try:
        db.table("approved_articles").update({"topic": "🚨 Top News"}).eq("article_id", top["id"]).execute()
    except Exception as exc:
        logging.warning("flag_top_news: approved_articles update failed (may not exist yet): %s", exc)

    logging.info(
        "flag_top_news: '%s' ← originally [%s] (I=%s U=%s)",
        (top.get("title") or "")[:70],
        top.get("topic"),
        top.get("score_importance"),
        top.get("score_urgency"),
    )


# ── Brief generator ───────────────────────────────────────────────────────────
BRIEF_GENERATOR_PROMPT = """You are the editor of DING News, a daily news app for readers who want \
to be informed in under 10 minutes. Today's deck has been finalized — \
your job is to write the brief card that opens the deck.

Input: the day's approved articles (titles + balanced_summary + topic) \
in the order they will appear (sorted by rank_score DESC).

Produce a JSON object with these fields:

- "editorial_opener": one short opener. "Good morning." is the default. \
  Vary it occasionally for tone — "Heavy news day." on weeks with major \
  events; "Quieter Tuesday." on slow days. Maximum 4 words.

- "brief_body": 2-3 sentences (40-60 words total) summarizing the day's \
  most significant stories in flowing prose. Reference 2-3 specific stories \
  by topic, not by repeating the headlines. Write in the voice of a \
  curator addressing a friend, not a wire service.

- "transition_line": one short line that hands off to the article cards. \
  Mention the count. Example: "8 stories ahead. Let's get into it."

- "topic_chips": array of topic names that appear in today's deck, in the \
  order they'll appear. No duplicates.

- "ai_confidence": 1-5, your confidence that the brief accurately \
  represents the day's articles without overstating, editorializing, or \
  missing the most important story. 5 means: no concerns, can ship \
  without human review.

Hard rules:
- Do not editorialize beyond what the articles themselves say.
- Do not introduce facts not in the input articles.
- Return JSON only, no prose wrapper.

Input articles for {date}:
{indexed_articles}"""


def generate_brief(claude_client, db, today_str: str) -> bool:
    """Generate the daily brief from today's approved articles. Returns True on success."""
    try:
        approved = (
            db.table("approved_articles")
            .select("id, topic, title, balanced_summary, why_it_matters, score_importance, score_urgency, score_interest")
            .eq("article_date", today_str)
            .order("rank_score", desc=True)
            .limit(10)
            .execute()
        )
    except Exception as exc:
        logging.error("Failed to fetch approved articles for brief: %s", exc)
        return False

    articles = approved.data
    if not articles:
        logging.info("No approved articles for %s — skipping brief generation.", today_str)
        return False

    # Build indexed article list for the prompt
    indexed_parts = []
    for i, a in enumerate(articles):
        indexed_parts.append(
            f"[{i}] Topic: {a['topic']}\n"
            f"    Title: {a['title']}\n"
            f"    Summary: {a['balanced_summary']}\n"
        )
    indexed_articles = "\n".join(indexed_parts)

    prompt = BRIEF_GENERATOR_PROMPT.format(
        date=today_str,
        indexed_articles=indexed_articles,
    )

    t0 = time.monotonic()
    response = None
    error_msg = None
    try:
        def _call():
            return claude_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

        response = with_retry(_call)
    except Exception as e:
        error_msg = str(e)
        logging.error("Claude call failed for brief generation: %s", e)
    finally:
        duration_ms = int((time.monotonic() - t0) * 1000)
        log_call(
            db,
            call_type="brief_generator",
            topic=None,
            response=response,
            duration_ms=duration_ms,
            success=(response is not None),
            error_message=error_msg,
        )

    if response is None:
        return False

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw   = "\n".join(lines[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.split("\n")[:-1])
    raw = raw.strip()

    try:
        brief = json.loads(raw)
        if not isinstance(brief, dict):
            raise ValueError("Expected JSON object")
    except Exception as e:
        logging.error("Failed to parse brief JSON: %s", e)
        logging.debug("Raw brief response: %s", raw[:500])
        return False

    ai_confidence = brief.get("ai_confidence", 0)
    now_iso = datetime.now(timezone.utc).isoformat()

    # Brief routing: confidence >= 4 → auto-approve (matches article threshold)
    upsert_row = {
        "brief_date":       today_str,
        "editorial_opener": brief.get("editorial_opener"),
        "brief_body":       brief.get("brief_body"),
        "transition_line":  brief.get("transition_line"),
        "topic_chips":      brief.get("topic_chips", []),
        "ai_confidence":    ai_confidence,
        "approved_at":      now_iso if ai_confidence >= 4 else None,
        "approved_by":      "ai_auto" if ai_confidence >= 4 else None,
    }

    try:
        db.table("daily_briefs").upsert(
            upsert_row,
            on_conflict="brief_date",
        ).execute()
        status = "auto-approved" if ai_confidence == 5 else "pending human review"
        logging.info("Brief for %s saved (%s).", today_str, status)
        return True
    except Exception as exc:
        logging.error("Failed to upsert daily_briefs: %s", exc)
        return False


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*60}")
    print(f"  DING.AI Pipeline Engine — {date.today().isoformat()}")
    print(f"{'='*60}\n")

    # Validate required secrets
    missing = []
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if not TAVILY_API_KEY:
        missing.append("TAVILY_API_KEY")
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_KEY:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

    # Init clients
    claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
    db            = create_client(SUPABASE_URL, SUPABASE_KEY)

    today_str       = date.today().isoformat()
    today_month_year = date.today().strftime("%B %Y")

    # Step 1: Build recent-coverage context for duplicate detection.
    # Primary: approved article titles from Supabase (authoritative — what we've
    # actually published/approved). Fallback: JSON history file headlines.
    print("Building recent coverage context…")
    approved_context = get_recent_approved_context(db)
    history          = load_history()
    history_headlines = get_recent_headlines(history)
    # Merge; approved context takes precedence (dedupe by content isn't needed —
    # Claude receives both as a flat list and uses semantic judgment).
    recent_headlines = approved_context + [h for h in history_headlines if h not in approved_context]
    print(f"  {len(approved_context)} approved titles + {len(history_headlines)} history headlines = {len(recent_headlines)} total")

    # Step 2: Fetch all 5 sections from Tavily
    print("\nFetching news via Tavily…")
    articles_by_section: dict = {}
    for section_name, query in SECTIONS:
        full_query = f"{query} {today_month_year}"
        print(f"  Searching: {section_name}…")
        articles_by_section[section_name] = search_news(tavily_client, full_query)
        print(f"  → {len(articles_by_section[section_name])} articles found")

    # Step 3: Persist fetched articles to Supabase
    print("\nPersisting fetched articles…")
    url_mapping = persist_fetched_articles(db, articles_by_section)

    # Step 4: Idempotency check — fetch only unprocessed articles per topic
    # Build {topic: {url: article_id}} for articles still in pending status
    print("\nChecking for unprocessed articles…")
    try:
        unprocessed = (
            db.table("articles")
            .select("id, topic, source_urls")
            .eq("status", "pending")
            .eq("article_date", today_str)
            .execute()
        )
        # Build a lookup: {topic: {url: article_id}} from DB (includes pre-existing)
        db_mapping: dict = {}
        for row in unprocessed.data:
            t = row["topic"]
            db_mapping.setdefault(t, {})
            for u in (row.get("source_urls") or []):
                db_mapping[t][u] = row["id"]
        # Merge with url_mapping (newly inserted this run)
        for topic, url_dict in url_mapping.items():
            db_mapping.setdefault(topic, {})
            db_mapping[topic].update(url_dict)
    except Exception as exc:
        logging.error("Failed to fetch unprocessed articles: %s — using in-memory mapping.", exc)
        db_mapping = url_mapping

    # Step 5: For each topic, call process_topic
    print("\nRunning article processor (1 Claude call per topic)…")
    for topic, articles in articles_by_section.items():
        topic_url_map = db_mapping.get(topic, {})
        if not topic_url_map:
            logging.info("  No unprocessed articles for topic %r — skipping.", topic)
            continue

        # Filter articles to only those with a pending DB row (unprocessed)
        pending_articles = [a for a in articles if a.get("url", "") in topic_url_map]
        if not pending_articles:
            logging.info("  No pending articles for topic %r — skipping.", topic)
            continue

        print(f"  Processing topic: {topic} ({len(pending_articles)} articles)…")
        try:
            processed = process_topic(
                claude_client, db, topic, pending_articles, topic_url_map, recent_headlines
            )
            print(f"  → {len(processed)} articles processed")
        except Exception as exc:
            logging.error("  Topic %r failed: %s — skipping.", topic, exc)

    # Step 6: Flag the highest-importance article as 🚨 Top News
    print("\nFlagging top news story…")
    flag_top_news(db, today_str)

    # Step 7: Generate daily brief from today's approved articles
    print("\nGenerating daily brief…")
    brief_ok = generate_brief(claude_client, db, today_str)
    if brief_ok:
        print("  Brief generated successfully.")
    else:
        print("  Brief generation skipped or failed (check logs).")

    print(f"\n{'='*60}")
    print(f"  Pipeline complete for {today_str}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
