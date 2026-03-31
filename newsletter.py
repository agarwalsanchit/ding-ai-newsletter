"""
DING.AI Newsletter Engine
Runs via GitHub Actions daily. Requires no local machine.

Dependencies:  anthropic, tavily-python, requests
Environment variables (set as GitHub Secrets):
  ANTHROPIC_API_KEY    — from platform.anthropic.com
  TAVILY_API_KEY       — from app.tavily.com (free, 1000 searches/month)
  GMAIL_ADDRESS        — your Gmail address (e.g. sanchitpurdue@gmail.com)
  GMAIL_APP_PASSWORD   — Gmail App Password (Google Account → Security → App Passwords)
  SEND_MODE            — "send" to send to all subscribers, "draft" to only save HTML (default: draft)
"""

import anthropic
import json
import os
import re
import smtplib
import sys
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from tavily import TavilyClient

# ── Config ────────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY")
TAVILY_API_KEY     = os.environ.get("TAVILY_API_KEY")
GMAIL_ADDRESS      = os.environ.get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
SEND_MODE          = os.environ.get("SEND_MODE", "draft")  # "draft" | "send"

HISTORY_FILE     = "history/newsletter_history.json"
OUTPUT_FILE      = "history/today_newsletter.html"
SUBSCRIBERS_FILE = "subscribers.json"

SECTIONS = [
    ("🚨 Top News",                    "breaking top news today"),
    ("🌍 Geopolitics & World Affairs", "geopolitics world affairs international news today"),
    ("💼 Business & Finance",          "business finance markets economy news today"),
    ("🔬 Science & Technology",        "science technology AI innovation news today"),
    ("🎾 Sports & Entertainment",      "sports entertainment news today"),
    ("🏛 Society & Culture",           "society culture social trends news today"),
]

# ── Subscribers ───────────────────────────────────────────────────────────────

def load_subscribers() -> list:
    """Load subscriber list from subscribers.json in the repo root."""
    if not os.path.exists(SUBSCRIBERS_FILE):
        print(f"⚠️  {SUBSCRIBERS_FILE} not found — no subscribers to send to.")
        return []
    with open(SUBSCRIBERS_FILE) as f:
        try:
            data = json.load(f)
            subscribers = data if isinstance(data, list) else data.get("subscribers", [])
            return [s for s in subscribers if "@" in str(s)]
        except json.JSONDecodeError:
            print(f"❌ Could not parse {SUBSCRIBERS_FILE}")
            return []


# ── History ───────────────────────────────────────────────────────────────────

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
    history = [e for e in history if e.get("date") != today_str]
    history.append({"date": today_str, "headlines": new_headlines})
    cutoff = (date.today() - timedelta(days=7)).isoformat()
    history = [e for e in history if e.get("date", "") >= cutoff]
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)
    print(f"✅ History updated — {len(history)} days stored")


def get_recent_headlines(history):
    cutoff = (date.today() - timedelta(days=3)).isoformat()
    recent = [e for e in history if e.get("date", "") >= cutoff]
    headlines = []
    for entry in recent:
        headlines.extend(entry.get("headlines", []))
    return headlines


# ── News fetching ─────────────────────────────────────────────────────────────

def search_news(tavily: TavilyClient, query: str, max_results: int = 6) -> list:
    try:
        results = tavily.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
            include_raw_content=False,
            days=2,
            topic="news",
        )
        return results.get("results", [])
    except Exception as e:
        print(f"  ⚠️  Tavily search failed for '{query}': {e}")
        return []


def build_news_context(articles_by_section: dict) -> str:
    context = ""
    for section_name, articles in articles_by_section.items():
        context += f"\n\n### {section_name}\n"
        if not articles:
            context += "  (no results found for this section)\n"
            continue
        for a in articles:
            title    = a.get("title", "Untitled")
            snippet  = a.get("content", a.get("snippet", ""))[:400]
            url      = a.get("url", "")
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
    if html.startswith("```"):
        html = "\n".join(html.split("\n")[1:])
    if html.endswith("```"):
        html = "\n".join(html.split("\n")[:-1])
    return html.strip()


def extract_headlines_from_html(html: str) -> list:
    pattern = r'color:#1a3a6b[^>]*>([^<]{20,})<'
    matches = re.findall(pattern, html)
    return [m.strip() for m in matches if len(m.strip()) > 20][:20]


# ── Gmail sending ─────────────────────────────────────────────────────────────

def send_via_gmail(html: str, subscribers: list) -> int:
    """
    Send newsletter HTML to each subscriber via Gmail SMTP.
    Returns the number of emails successfully sent.
    """
    today = date.today()
    subject = f"Ding! Your {today.strftime('%A')} briefing is here 🗞️"

    print(f"📬 Sending to {len(subscribers)} subscriber(s) via Gmail SMTP...")

    sent = 0
    failed = []

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)

        for recipient in subscribers:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"]    = f"DING.AI <{GMAIL_ADDRESS}>"
                msg["To"]      = recipient
                msg.attach(MIMEText(html, "html"))
                server.sendmail(GMAIL_ADDRESS, recipient, msg.as_string())
                print(f"   ✅ Sent → {recipient}")
                sent += 1
            except Exception as e:
                print(f"   ❌ Failed → {recipient}: {e}")
                failed.append(recipient)

    if failed:
        print(f"\n⚠️  {len(failed)} send(s) failed: {failed}")

    return sent


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*60}")
    print(f"  DING.AI Newsletter Engine — {date.today().isoformat()}")
    print(f"{'='*60}\n")

    # Validate required secrets
    required = {
        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
        "TAVILY_API_KEY":    TAVILY_API_KEY,
    }
    if SEND_MODE == "send":
        required["GMAIL_ADDRESS"]      = GMAIL_ADDRESS
        required["GMAIL_APP_PASSWORD"] = GMAIL_APP_PASSWORD

    missing = [k for k, v in required.items() if not v]
    if missing:
        print(f"❌ Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

    # Init clients
    claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

    # Step 1: Load history
    print("📂 Loading headline history...")
    history = load_history()
    recent_headlines = get_recent_headlines(history)
    print(f"   Found {len(recent_headlines)} recent headlines for deduplication")

    # Step 2: Fetch news
    print("\n🔍 Fetching news via Tavily...")
    articles_by_section = {}
    for section_name, query in SECTIONS:
        today_month_year = date.today().strftime("%B %Y")
        full_query = f"{query} {today_month_year}"
        print(f"   Searching: {section_name}...")
        articles_by_section[section_name] = search_news(tavily_client, full_query)
        print(f"   → {len(articles_by_section[section_name])} articles found")

    news_context = build_news_context(articles_by_section)

    # Step 3: Generate newsletter
    print()
    html = generate_newsletter_html(claude_client, news_context, recent_headlines)
    print(f"   Generated {len(html):,} characters of HTML")

    # Step 4: Save HTML to repo
    os.makedirs("history", exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        f.write(html)
    print(f"💾 HTML saved to {OUTPUT_FILE}")

    # Step 5: Send or draft
    print()
    if SEND_MODE == "send":
        subscribers = load_subscribers()
        if not subscribers:
            print("⚠️  No subscribers found — skipping send. Add emails to subscribers.json.")
        else:
            sent = send_via_gmail(html, subscribers)
            print(f"\n✅ Sent to {sent}/{len(subscribers)} subscriber(s).")
    else:
        print(f"📝 SEND_MODE=draft — newsletter saved to {OUTPUT_FILE}. Not emailed.")
        print(f"   To send for real, set SEND_MODE=send in GitHub Secrets.")

    # Step 6: Update history
    new_headlines = extract_headlines_from_html(html)
    save_history(history, new_headlines)

    print(f"\n{'='*60}")
    print(f"  ✅ Done! Mode: {SEND_MODE} | Headlines stored: {len(new_headlines)}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
