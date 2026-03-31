"""
DING.AI Newsletter Engine
Runs via GitHub Actions daily. Requires no local machine.

Dependencies:  anthropic, requests, tavily-python
Environment variables (set as GitHub Secrets):
  ANTHROPIC_API_KEY       — from platform.anthropic.com
  TAVILY_API_KEY          — from app.tavily.com (free, 1000 searches/month)
  BEEHIIV_API_KEY         — from Beehiiv dashboard → Settings → API
  BEEHIIV_PUBLICATION_ID  — from Beehiiv dashboard → Settings → Publication
  SEND_MODE               — "send" to send immediately, "draft" to review first (default: draft)
"""

import anthropic
import requests
import json
import os
import sys
from datetime import date, datetime, timedelta
from tavily import TavilyClient

# ── Config ────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY      = os.environ.get("ANTHROPIC_API_KEY")
TAVILY_API_KEY         = os.environ.get("TAVILY_API_KEY")
BEEHIIV_API_KEY        = os.environ.get("BEEHIIV_API_KEY")
BEEHIIV_PUBLICATION_ID = os.environ.get("BEEHIIV_PUBLICATION_ID")
SEND_MODE              = os.environ.get("SEND_MODE", "draft")  # "draft" | "send"

HISTORY_FILE = "history/newsletter_history.json"
OUTPUT_FILE  = "history/today_newsletter.html"

SECTIONS = [
    ("🚨 Top News",                    "breaking top news today"),
    ("🌍 Geopolitics & World Affairs", "geopolitics world affairs international news today"),
    ("💼 Business & Finance",          "business finance markets economy news today"),
    ("🔬 Science & Technology",        "science technology AI innovation news today"),
    ("🎾 Sports & Entertainment",      "sports entertainment news today"),
    ("🏛 Society & Culture",           "society culture social trends news today"),
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_history(history, new_headlines):
    today_str = date.today().isoformat()
    # Remove entry for today if it exists (re-run safety)
    history = [e for e in history if e.get("date") != today_str]
    history.append({"date": today_str, "headlines": new_headlines})
    # Keep only last 7 days
    cutoff = (date.today() - timedelta(days=7)).isoformat()
    history = [e for e in history if e.get("date", "") >= cutoff]
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)
    print(f"✅ History updated — {len(history)} days stored")


def get_recent_headlines(history):
    """Return headlines from the last 3 days for deduplication."""
    cutoff = (date.today() - timedelta(days=3)).isoformat()
    recent = [e for e in history if e.get("date", "") >= cutoff]
    headlines = []
    for entry in recent:
        headlines.extend(entry.get("headlines", []))
    return headlines


def search_news(tavily: TavilyClient, query: str, max_results: int = 6) -> list:
    """Fetch recent news for a single category via Tavily."""
    try:
        results = tavily.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
            include_raw_content=False,
            days=2,  # last 48 hours
            topic="news",
        )
        return results.get("results", [])
    except Exception as e:
        print(f"  ⚠️  Tavily search failed for '{query}': {e}")
        return []


def build_news_context(articles_by_section: dict) -> str:
    """Format search results into a clean context block for Claude."""
    context = ""
    for section_name, articles in articles_by_section.items():
        context += f"\n\n### {section_name}\n"
        if not articles:
            context += "  (no results found for this section)\n"
            continue
        for a in articles:
            title   = a.get("title", "Untitled")
            snippet = a.get("content", a.get("snippet", ""))[:400]
            url     = a.get("url", "")
            pub_date = a.get("published_date", "recent")
            context += f"- **{title}** ({pub_date})\n"
            context += f"  {snippet}\n"
            context += f"  Source: {url}\n"
    return context


# ── Newsletter generation ──────────────────────────────────────────────────────

NEWSLETTER_PROMPT = """You are the DING.AI newsletter engine. Today is {today}. Write the daily "Signal Over Noise" morning briefing.

## TODAY'S NEWS (from web search)
{news_context}

## RECENT HEADLINES (last 3 days — DO NOT duplicate unless major new development)
{recent_headlines}

## INSTRUCTIONS
- Write 2-3 stories per section, using ONLY stories from the news provided above
- If a story overlaps with recent headlines, skip it unless there is a significant new development
- For each story: write a punchy headline, 2-3 sentence factual summary with source names in italics, and a "Why it matters:" line that names the actual consequence
- Intro paragraph: 2-3 sentences teasing the biggest stories of the day, conversational tone
- Omit any section where no good stories were found

## HTML FORMAT — CRITICAL RULES
- Use ONLY inline styles. Zero CSS classes. Zero <style> blocks.
- Table-based layout (not divs) for all structural elements
- All special characters as HTML entities (& → &amp;, quotes → &#34;, em dash → &#8212;)
- No placeholder text remaining

Use this exact HTML template and fill in all [PLACEHOLDERS]:

<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head><body style="margin:0;padding:0;background-color:#eef1f8;font-family:Arial,Helvetica,sans-serif;"><table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#eef1f8;"><tr><td align="center" style="padding:24px 12px;"><table width="640" cellpadding="0" cellspacing="0" border="0" style="max-width:640px;width:100%;background-color:#ffffff;border-radius:4px;">
<tr><td align="center" style="padding:36px 40px 4px;"><div style="font-size:34px;font-weight:900;letter-spacing:1px;color:#0d1b2a;font-family:Georgia,serif;">DING<span style="color:#2d7dd2;">.AI</span></div></td></tr>
<tr><td align="center" style="padding:0 40px 6px;"><div style="font-size:13px;color:#666;font-style:italic;letter-spacing:0.5px;">Signal Over Noise</div></td></tr>
<tr><td align="center" style="padding:0 40px 16px;"><div style="font-size:12px;color:#999;letter-spacing:0.5px;">{today}</div></td></tr>
<tr><td style="padding:0 40px;"><table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="border-top:2px solid #2d7dd2;font-size:0;line-height:0;">&nbsp;</td></tr></table></td></tr>
<tr><td style="padding:28px 40px 20px;"><div style="font-size:17px;font-weight:700;color:#0d1b2a;margin-bottom:12px;">Hi Human!</div><p style="font-size:15px;color:#444;line-height:1.75;margin:0;">[INTRO]</p></td></tr>
[SECTIONS]
<tr><td style="padding:28px 40px 0;"><table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="border-top:2px solid #2d7dd2;font-size:0;line-height:0;">&nbsp;</td></tr></table></td></tr>
<tr><td align="center" style="padding:28px 40px 8px;"><p style="font-size:14px;font-weight:700;color:#0d1b2a;margin:0;">Thanks for reading today&#39;s edition of <a href="#" style="color:#2d7dd2;text-decoration:none;">DING.AI</a> &#8212; where we cut through the noise to bring you the signal.</p></td></tr>
<tr><td align="center" style="padding:0 40px 8px;"><p style="font-size:13px;color:#666;margin:0;line-height:1.6;">Got feedback or a story tip? Just hit reply.</p></td></tr>
<tr><td align="center" style="padding:0 40px 36px;"><p style="font-size:11px;color:#aaa;margin:0;">&#169; 2026 DING.AI &#183; All rights reserved</p></td></tr>
</table></td></tr></table></body></html>

Each [SECTION] block looks like:
<tr><td style="padding:4px 40px 0;"><div style="font-size:20px;font-weight:700;color:#d4622a;margin-bottom:20px;">[EMOJI] [Section Title]</div>
  <div style="margin-bottom:26px;">
    <div style="font-size:15px;font-weight:700;color:#1a3a6b;line-height:1.45;margin-bottom:10px;">[Story Headline]</div>
    <p style="font-size:14px;color:#333;line-height:1.75;margin:0 0 8px;">[Summary. <em>([Sources])</em>]</p>
    <p style="font-size:13.5px;color:#8899aa;line-height:1.65;margin:4px 0 0;"><strong style="color:#8899aa;">Why it matters:</strong> [Consequence]</p>
  </div>
</td></tr>
<tr><td style="padding:20px 40px 0;"><table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="border-top:1px solid #e8ecf2;font-size:0;line-height:0;">&nbsp;</td></tr></table></td></tr>

Return ONLY the complete HTML. No markdown fences. No explanation."""


def generate_newsletter_html(claude_client, news_context: str, recent_headlines: list) -> str:
    today_str = date.today().strftime("%A, %B %d, %Y")
    recent_str = json.dumps(recent_headlines, indent=2) if recent_headlines else "None — first edition!"

    prompt = NEWSLETTER_PROMPT.format(
        today=today_str,
        news_context=news_context,
        recent_headlines=recent_str,
    )

    print("🤖 Calling Claude API to generate newsletter...")
    message = claude_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8096,
        messages=[{"role": "user", "content": prompt}],
    )
    html = message.content[0].text.strip()
    # Strip markdown code fences if Claude wrapped it anyway
    if html.startswith("```"):
        html = "\n".join(html.split("\n")[1:])
    if html.endswith("```"):
        html = "\n".join(html.split("\n")[:-1])
    return html.strip()


def extract_headlines_from_html(html: str) -> list:
    """
    Rough extraction of story headlines from the generated HTML
    for deduplication history. Looks for the story headline div pattern.
    """
    import re
    pattern = r'color:#1a3a6b[^>]*>([^<]{20,})<'
    matches = re.findall(pattern, html)
    return [m.strip() for m in matches if len(m.strip()) > 20][:20]


# ── Beehiiv integration ───────────────────────────────────────────────────────

def send_via_beehiiv(html: str, send_mode: str) -> str:
    """
    Create a Beehiiv post and either send it immediately or save as draft.
    Returns the post ID.
    send_mode: "send" → sends to all subscribers immediately
               "draft" → saves as draft for review in Beehiiv dashboard
    """
    today = date.today()
    subject = f"Ding! Your {today.strftime('%A')} briefing is here 🗞️"
    preview = f"Signal Over Noise — {today.strftime('%B %d, %Y')}"

    # Map SEND_MODE to Beehiiv status
    status = "confirmed" if send_mode == "send" else "draft"

    print(f"📬 Creating Beehiiv post (status: {status})...")

    create_resp = requests.post(
        f"https://api.beehiiv.com/v2/publications/{BEEHIIV_PUBLICATION_ID}/posts",
        headers={
            "Authorization": f"Bearer {BEEHIIV_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "subject_line": subject,
            "preview_text": preview,
            "body": html,
            "status": status,
            "audience": "all",
            "send_at": None,  # send immediately when status=confirmed
        },
        timeout=30,
    )

    if create_resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Beehiiv post creation failed ({create_resp.status_code}): {create_resp.text}"
        )

    data = create_resp.json().get("data", {})
    post_id = data.get("id", "unknown")
    post_url = data.get("url", "")

    if send_mode == "send":
        print(f"✅ Newsletter sent via Beehiiv! Post ID: {post_id}")
    else:
        print(f"✅ Draft created in Beehiiv. Review at: https://app.beehiiv.com")
        print(f"   Post ID: {post_id}")

    return post_id


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*60}")
    print(f"  DING.AI Newsletter Engine — {date.today().isoformat()}")
    print(f"{'='*60}\n")

    # Validate required secrets
    missing = [k for k, v in {
        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
        "TAVILY_API_KEY": TAVILY_API_KEY,
        "BEEHIIV_API_KEY": BEEHIIV_API_KEY,
        "BEEHIIV_PUBLICATION_ID": BEEHIIV_PUBLICATION_ID,
    }.items() if not v]
    if missing:
        print(f"❌ Missing required environment variables: {', '.join(missing)}")
        print("   Add these as GitHub Secrets in your repo settings.")
        sys.exit(1)

    # Init clients
    claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

    # Step 1: Load history
    print("📂 Loading headline history...")
    history = load_history()
    recent_headlines = get_recent_headlines(history)
    print(f"   Found {len(recent_headlines)} recent headlines for deduplication")

    # Step 2: Fetch news for all sections
    print("\n🔍 Fetching news via Tavily...")
    articles_by_section = {}
    for section_name, query in SECTIONS:
        today_month_year = date.today().strftime("%B %Y")
        full_query = f"{query} {today_month_year}"
        print(f"   Searching: {section_name}...")
        articles_by_section[section_name] = search_news(tavily_client, full_query)
        total = len(articles_by_section[section_name])
        print(f"   → {total} articles found")

    news_context = build_news_context(articles_by_section)

    # Step 3: Generate newsletter HTML
    print()
    html = generate_newsletter_html(claude_client, news_context, recent_headlines)
    print(f"   Generated {len(html):,} characters of HTML")

    # Step 4: Save HTML locally in repo
    os.makedirs("history", exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        f.write(html)
    print(f"💾 HTML saved to {OUTPUT_FILE}")

    # Step 5: Send via Beehiiv
    print()
    post_id = send_via_beehiiv(html, SEND_MODE)

    # Step 6: Update headline history
    new_headlines = extract_headlines_from_html(html)
    save_history(history, new_headlines)

    print(f"\n{'='*60}")
    print(f"  ✅ Done! Beehiiv post ID: {post_id}")
    print(f"  Mode: {SEND_MODE} | Headlines stored: {len(new_headlines)}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
