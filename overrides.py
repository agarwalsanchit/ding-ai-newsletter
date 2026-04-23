"""
overrides.py
Editor-controlled newsletter overrides.

Pulls a Google Sheet tab ("Overrides") listing topics or specific article URLs
the editor wants covered in the next edition. Hard overrides must appear;
soft overrides are nudges. URL overrides are fetched and fact-checked against
Tavily before being passed to Claude.

Expected sheet columns (case-insensitive, extras ignored):
  Topic     — e.g. "IPL 2026 playoffs"
  URL       — optional link to a specific article to cover
  Strength  — "hard" (must include) or "soft" (nudge). Default: soft
  Section   — optional: which section to place it in (matches a SECTIONS label)
  Run Date  — optional YYYY-MM-DD; blank = always active, otherwise only on that date
  Notes     — optional free-text hint for the editor to the writer

Usage from newsletter.py:
  from overrides import fetch_and_process_overrides
  override_context = fetch_and_process_overrides(claude_client, tavily_client)
"""
import csv
import html as html_lib
import io
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import date


# ── Sheet fetching ───────────────────────────────────────────────────────────
def fetch_overrides_csv(url: str) -> list[dict]:
    """Pull the Overrides tab CSV from a Google Sheets 'publish to web' link."""
    if not url:
        return []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(content)))
    except Exception as e:
        print(f"  ⚠️  Could not fetch overrides sheet: {e}")
        return []


def _col(row: dict, *candidates: str) -> str:
    """Case-insensitive column lookup with whitespace tolerance."""
    for key in row:
        norm = key.lower().strip()
        for c in candidates:
            if c.lower().strip() == norm:
                return (row.get(key) or "").strip()
    return ""


def parse_overrides(rows: list[dict], today_iso: str) -> list[dict]:
    """Normalize sheet rows into override dicts, filtering by Run Date."""
    out = []
    for row in rows:
        topic = _col(row, "Topic")
        url = _col(row, "URL", "Url", "Link")
        if not topic and not url:
            continue
        strength = _col(row, "Strength").lower() or "soft"
        if strength not in ("hard", "soft"):
            strength = "soft"
        run_date = _col(row, "Run Date", "RunDate", "Date")
        if run_date and run_date != today_iso:
            # Row is scheduled for a different day — skip
            continue
        out.append({
            "topic":    topic,
            "url":      url,
            "strength": strength,
            "section":  _col(row, "Section"),
            "notes":    _col(row, "Notes"),
        })
    return out


# ── Article fetching ─────────────────────────────────────────────────────────
_SKIP_TAGS_RE = re.compile(
    r'<(script|style|noscript|nav|footer|header|aside|form|iframe|svg)[^>]*>.*?</\1>',
    re.DOTALL | re.IGNORECASE,
)


def fetch_article_text(url: str, max_chars: int = 8000) -> str | None:
    """Fetch a URL and return readable body text, or None on failure/paywall."""
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; DING.AI/1.0; +https://agarwalsanchit.github.io/ding-ai-newsletter/)",
            "Accept": "text/html,application/xhtml+xml",
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            ctype = resp.headers.get("Content-Type", "")
            if "text/html" not in ctype and "text/plain" not in ctype:
                print(f"  ⚠️  Skipping non-HTML content at {url} ({ctype})")
                return None
            raw = resp.read(2_000_000).decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  ⚠️  Could not fetch {url}: {e}")
        return None

    # Try to isolate <article>/<main> if present, else fall back to <body>
    body_match = re.search(r'<(article|main)[^>]*>(.*?)</\1>', raw, re.DOTALL | re.IGNORECASE)
    body = body_match.group(2) if body_match else raw

    # Strip noisy tags
    txt = _SKIP_TAGS_RE.sub(' ', body)
    # Drop remaining HTML tags
    txt = re.sub(r'<[^>]+>', ' ', txt)
    txt = html_lib.unescape(txt)
    txt = re.sub(r'\s+', ' ', txt).strip()

    if len(txt) < 200:
        # Too short — likely paywalled or JS-rendered
        return None
    return txt[:max_chars]


# ── Claim extraction + verification ──────────────────────────────────────────
def extract_claims(claude_client, article_text: str, url: str) -> list[str]:
    """Ask Claude to surface the 3–5 most important verifiable claims."""
    prompt = (
        "You are a fact-checking assistant. Read the article below and list the "
        "3 to 5 most important factual claims it makes — specific numbers, dates, "
        "events, or statements attributed to named people. Avoid opinion or analysis. "
        "Return ONLY a JSON array of strings, nothing else.\n\n"
        f"URL: {url}\n\n"
        f"ARTICLE TEXT:\n{article_text}"
    )
    try:
        msg = claude_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = "\n".join(raw.split("\n")[:-1])
        claims = json.loads(raw.strip())
        if isinstance(claims, list):
            return [str(c).strip() for c in claims if str(c).strip()][:5]
    except Exception as e:
        print(f"  ⚠️  Claim extraction failed: {e}")
    return []


def verify_claim(tavily_client, claim: str) -> dict:
    """Run a Tavily search for the claim. Claude will later judge corroboration."""
    try:
        res = tavily_client.search(
            query=claim,
            max_results=4,
            search_depth="basic",
            include_raw_content=False,
        ).get("results", [])
    except Exception as e:
        print(f"  ⚠️  Verify search failed: {e}")
        res = []
    return {
        "claim": claim,
        "evidence": [
            {
                "title": (r.get("title") or "")[:180],
                "url":   r.get("url", ""),
                "text":  ((r.get("content") or r.get("snippet") or "")[:350]),
            }
            for r in res[:4]
        ],
    }


def fact_check_article(claude_client, tavily_client, url: str) -> dict:
    """Fetch article → extract claims → cross-reference via Tavily."""
    text = fetch_article_text(url)
    if not text:
        return {"url": url, "ok": False, "reason": "fetch_failed_or_paywall"}
    claims = extract_claims(claude_client, text, url)
    verified = [verify_claim(tavily_client, c) for c in claims] if claims else []
    return {
        "url":          url,
        "ok":           True,
        "article_text": text[:2500],
        "claims":       verified,
    }


# ── Context builder ──────────────────────────────────────────────────────────
def _search_news_for_topic(tavily_client, topic: str, max_results: int = 5) -> list[dict]:
    """Dedicated Tavily news search for a hard topic override."""
    try:
        return tavily_client.search(
            query=topic,
            max_results=max_results,
            search_depth="advanced",
            include_raw_content=False,
            days=7,
            topic="news",
        ).get("results", [])
    except Exception as e:
        print(f"  ⚠️  Tavily topic search failed for '{topic}': {e}")
        return []


def build_override_context(claude_client, tavily_client, overrides: list[dict]) -> str:
    """Produce the prompt fragment describing overrides + supporting evidence."""
    if not overrides:
        return ""

    hard = [o for o in overrides if o["strength"] == "hard"]
    soft = [o for o in overrides if o["strength"] == "soft"]
    parts: list[str] = []

    parts.append("\n## EDITORIAL OVERRIDES (from the editor)\n")
    parts.append(
        "These items have been selected by the editor. Hard overrides MUST appear "
        "in the newsletter as their own dedicated items regardless of what else "
        "was in the news today, and even if similar topics appear in the last-3-days "
        "dedup list. Soft overrides should be included only if substantive.\n"
    )

    # ── Hard overrides ───────────────────────────────────────────
    if hard:
        parts.append("\n### MUST INCLUDE (hard overrides)\n")
        for i, o in enumerate(hard, 1):
            parts.append(f"\n--- Hard Override #{i} ---\n")
            if o["topic"]:
                parts.append(f"Topic: {o['topic']}\n")
            if o["section"]:
                parts.append(f"Preferred section: {o['section']}\n")
            if o["notes"]:
                parts.append(f"Editor notes: {o['notes']}\n")

            if o["url"]:
                # URL-based override → fact-check workflow
                parts.append(f"Primary source: {o['url']}\n")
                print(f"  🔍 Fact-checking override URL: {o['url']}")
                fc = fact_check_article(claude_client, tavily_client, o["url"])
                if fc["ok"]:
                    parts.append("\nArticle excerpt (use as primary source):\n")
                    parts.append(fc["article_text"] + "\n")
                    if fc["claims"]:
                        parts.append("\nFact-check evidence (cross-referenced via Tavily):\n")
                        for c in fc["claims"]:
                            parts.append(f"- CLAIM: {c['claim']}\n")
                            if not c["evidence"]:
                                parts.append("    (no independent corroboration found)\n")
                            for ev in c["evidence"]:
                                parts.append(
                                    f"    * {ev['title']} — {ev['url']}\n"
                                    f"      {ev['text'][:220]}\n"
                                )
                        parts.append(
                            "\nREQUIREMENT: When writing this item, add a short "
                            "\"Fact check:\" line (styled like the Why-it-matters line) "
                            "noting which key claims are corroborated by independent "
                            "sources vs. unverified. Do not include an item if the "
                            "core claims look fabricated.\n"
                        )
                else:
                    # Fallback: treat as topic seed
                    print(f"  ⚠️  URL fetch failed ({fc.get('reason')}); falling back to Tavily")
                    seed = o["topic"] or o["url"]
                    results = _search_news_for_topic(tavily_client, seed, max_results=5)
                    parts.append(
                        f"\n(Could not fetch the article directly — reason: "
                        f"{fc.get('reason')}. Treat as a topic and write from Tavily "
                        f"results below, linking back to the editor's source URL.)\n"
                    )
                    for r in results:
                        parts.append(
                            f"- {r.get('title','')} ({r.get('url','')})\n"
                            f"  {(r.get('content') or '')[:300]}\n"
                        )
            elif o["topic"]:
                # Topic-only hard override → dedicated Tavily search
                print(f"  🔍 Tavily search for hard topic: {o['topic']}")
                results = _search_news_for_topic(tavily_client, o["topic"])
                if not results:
                    parts.append(
                        "(No Tavily results found — write a brief, cautious item "
                        "based on general context and say the news is limited.)\n"
                    )
                else:
                    parts.append("\nSupporting sources (use these for the item):\n")
                    for r in results:
                        parts.append(
                            f"- {r.get('title','')} ({r.get('url','')})\n"
                            f"  {(r.get('content') or '')[:300]}\n"
                        )

    # ── Soft overrides ───────────────────────────────────────────
    if soft:
        parts.append("\n### PREFERRED COVERAGE (soft overrides)\n")
        parts.append(
            "Nudges from the editor. Include if substantive news exists; otherwise "
            "it is fine to skip.\n"
        )
        for o in soft:
            label = o["topic"] or o["url"]
            extras = []
            if o["section"]:
                extras.append(f"prefer {o['section']}")
            if o["notes"]:
                extras.append(o["notes"])
            suffix = f" ({'; '.join(extras)})" if extras else ""
            parts.append(f"- {label}{suffix}\n")

            if o["topic"]:
                results = _search_news_for_topic(tavily_client, o["topic"], max_results=3)
                for r in results[:3]:
                    parts.append(
                        f"    · {r.get('title','')} ({r.get('url','')}): "
                        f"{(r.get('content') or '')[:200]}\n"
                    )

    return "".join(parts)


def fetch_and_process_overrides(claude_client, tavily_client) -> str:
    """Top-level entry point for newsletter.py."""
    url = os.environ.get("OVERRIDES_SHEET_URL", "").strip()
    if not url:
        print("  (OVERRIDES_SHEET_URL not set — no editor overrides this run)")
        return ""
    rows = fetch_overrides_csv(url)
    overrides = parse_overrides(rows, date.today().isoformat())
    if not overrides:
        print("  (Overrides tab is empty or all rows are scheduled for a different day)")
        return ""
    print(f"  Found {len(overrides)} active override(s): "
          f"{sum(1 for o in overrides if o['strength']=='hard')} hard, "
          f"{sum(1 for o in overrides if o['strength']=='soft')} soft")
    return build_override_context(claude_client, tavily_client, overrides)
