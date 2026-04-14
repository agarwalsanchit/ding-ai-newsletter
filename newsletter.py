"""
DING.AI Newsletter Engine
Runs via GitHub Actions daily. Requires no local machine.

Dependencies:  anthropic, tavily-python, requests
Environment variables (set as GitHub Secrets):
  ANTHROPIC_API_KEY   — from platform.anthropic.com
  TAVILY_API_KEY      — from app.tavily.com (free, 1000 searches/month)
  GMAIL_ADDRESS       — your Gmail address (e.g. sanchitpurdue@gmail.com)
  GMAIL_APP_PASSWORD  — Gmail App Password (Google Account → Security → App Passwords)
  SEND_MODE           — "send" to send to all subscribers, "draft" to only save HTML (default: draft)
"""

import anthropic
import html as html_lib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from tavily import TavilyClient

# ── Config ───────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY")
TAVILY_API_KEY     = os.environ.get("TAVILY_API_KEY")
GMAIL_ADDRESS      = os.environ.get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
SEND_MODE          = os.environ.get("SEND_MODE", "draft")   # "draft" | "send"

HISTORY_FILE     = "history/newsletter_history.json"
OUTPUT_FILE      = "history/today_newsletter.html"
SUBSCRIBERS_FILE = "subscribers.json"
ARCHIVE_DIR      = "docs/issues"
ARCHIVE_INDEX    = "docs/issues/index.json"

SECTIONS = [
    ("🚨 Top News",                  "biggest breaking top news today site:reuters.com OR site:apnews.com OR site:bbc.com"),
    ("🌍 Geopolitics & World Affairs","geopolitics international conflict diplomacy world news today"),
    ("💼 Business & Finance",        "stock market economy business earnings finance news today"),
    ("🔬 Science & Technology",      "AI artificial intelligence science technology innovation research news today"),
    ("🎾 Sports & Entertainment",    "sports major games results entertainment celebrity news today"),
    ("🏛 Society & Culture",         "society culture politics social trends education news today"),
]

# ── Retry helper ─────────────────────────────────────────────────────────────
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
                print(f"  #⚠️  Attempt {attempt+1} failed: {e}. Retrying in {wait:.0f}s…")
                time.sleep(wait)
    raise last_err

# ── Subscribers ───────────────────────────────────────────────────────────────
def load_subscribers() -> list:
    """Load subscriber list from subscribers.json."""
    if not os.path.exists(SUBSCRIBERS_FILE):
        print(f"⚠️  {SUBSCRIBERS_FILE} not found — no subscribers to send to.")
        return []
    with open(SUBSCRIBERS_FILE) as f:
        try:
            data = json.load(f)
            subs = []
            for s in data:
                if isinstance(s, str) and "@" in s:
                    subs.append({"name": s.split("@")[0].capitalize(), "email": s})
                elif isinstance(s, dict) and "@" in s.get("email", ""):
                    subs.append({"name": s.get("name", "Reader"), "email": s["email"]})
            return subs
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

def save_history(history, new_headlines, sent_count: int = 0):
    today_str = date.today().isoformat()
    history   = [e for e in history if e.get("date") != today_str]
    history.append({
        "date":      today_str,
        "headlines": new_headlines,
        "sent":      sent_count,
    })
    cutoff  = (date.today() - timedelta(days=7)).isoformat()
    history = [e for e in history if e.get("date", "") >= cutoff]
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)
    print(f"✅ History updated — {len(history)} days stored")

def get_recent_headlines(history):
    cutoff  = (date.today() - timedelta(days=3)).isoformat()
    recent  = [e for e in history if e.get("date", "") >= cutoff]
    headlines = []
    for entry in recent:
        headlines.extend(entry.get("headlines", []))
    return headlines

# ── News fetching ─────────────────────────────────────────────────────────────
def search_news(tavily: TavilyClient, query: str, max_results: int = 6) -> list:
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
            context += f"- **{title}** ({pub_date})\n  {snippet}\n  Source: {url}\n"
    return context

# ── Newsletter generation ─────────────────────────────────────────────────────
NEWSLETTER_PROMPT = """You are the DING.AI newsletter engine. Today is {today}.
Write the daily "Signal Over Noise" morning briefing.

## TODAY'S NEWS (from web search)
{news_context}

## RECENT HEADLINES (last 3 days — DO NOT duplicate unless major new development)
{recent_headlines}

## INSTRUCTIONS
- Write 2-3 stories per section, using ONLY stories from the news provided above
- If a story overlaps with recent headlines, skip it unless there is a significant new development
- For each story: write a punchy headline, 2-3 sentence factual summary with source names in italics, and a "Why it matters:" line that names the actual consequence
- Intro paragraph: 2-3 sentences teasing the biggest stories of the day, conversational and slightly witty tone
- "Quick Hits" section: 5 crisp one-sentence bullets on notable stories that didn't make a full section
- Omit any section where no good stories were found

## HTML FORMAT — CRITICAL RULES
- Use ONLY inline styles. Zero CSS classes. Zero <style> blocks.
- Table-based layout (not divs) for all structural elements
- All special characters as HTML entities (& → &amp;, quotes → &#34;, em dash → &#8212;)
- No placeholder text remaining

## OUTPUT FORMAT
Return a JSON object with exactly two keys:
  "subject": "DING! Your {today} briefing is here"
  "html": "the complete HTML email starting with <!DOCTYPE html>"

Use this exact HTML template and fill in all [PLACEHOLDERS]:

<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head><body style="margin:0;padding:0;background-color:#eef1f8;font-family:Arial,Helvetica,sans-serif;"><table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#eef1f8;"><tr><td align="center" style="padding:24px 12px;"><table width="640" cellpadding="0" cellspacing="0" border="0" style="max-width:640px;width:100%;background-color:#ffffff;border-radius:4px;">
<tr><td align="center" style="padding:36px 40px 4px;"><div style="font-size:34px;font-weight:900;letter-spacing:1px;color:#0d1b2a;font-family:Georgia,serif;">DING<span style="color:#2d7dd2;">.AI</span></div></td></tr>
<tr><td align="center" style="padding:0 40px 6px;"><div style="font-size:13px;color:#666;font-style:italic;letter-spacing:0.5px;">Signal Over Noise</div></td></tr>
<tr><td align="center" style="padding:0 40px 16px;"><div style="font-size:12px;color:#999;letter-spacing:0.5px;">{today}</div></td></tr>
<tr><td style="padding:0 40px;"><table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="border-top:2px solid #2d7dd2;font-size:0;line-height:0;">&nbsp;</td></tr></table></td></tr>
<tr><td style="padding:28px 40px 20px;"><div style="font-size:17px;font-weight:700;color:#0d1b2a;margin-bottom:12px;">Hi [NAME]!</div><p style="font-size:15px;color:#444;line-height:1.75;margin:0;">[INTRO]</p></td></tr>
[SECTIONS]
[QUICK_HITS]
<tr><td style="padding:28px 40px 0;"><table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="border-top:2px solid #2d7dd2;font-size:0;line-height:0;">&nbsp;</td></tr></table></td></tr>
<tr><td style="padding:0 24px;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-top:2px solid #667eea;margin-top:24px;">
<tr><td style="padding:28px 0 0;text-align:center;">
<p style="font-size:16px;color:#333;font-weight:bold;margin:0 0 6px;font-family:Arial,sans-serif;">Thanks for reading DING&#8203;.AI &#8212; signal over noise, every morning.</p>
<p style="font-size:14px;color:#666;margin:0 0 20px;font-family:Arial,sans-serif;">Got feedback or a story tip? Just hit reply. Forward this to a friend who'd enjoy it.</p>
</td></tr>
<tr><td align="center" style="padding:0 0 24px;">
<!--[if mso]>
<table cellpadding="0" cellspacing="0" border="0" width="100%"><tr><td bgcolor="#764ba2" style="padding:24px;text-align:center;">
<![endif]-->
<div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);background-color:#764ba2;border-radius:10px;padding:24px;text-align:center;">
<p style="color:#ffffff;font-size:17px;font-weight:bold;margin:0 0 6px;font-family:Arial,sans-serif;">Enjoying DING&#8203;.AI? Share it!</p>
<p style="color:rgba(255,255,255,0.85);font-size:13px;margin:0 0 16px;font-family:Arial,sans-serif;">Know someone who'd love a daily AI briefing? Spread the word.</p>
<!--[if mso]>
<table cellpadding="0" cellspacing="0" border="0" align="center"><tr><td bgcolor="#ffffff" style="padding:10px 24px;text-align:center;">
<![endif]-->
<a href="https://agarwalsanchit.github.io/ding-ai-newsletter/#share" style="display:inline-block;background:#ffffff;color:#764ba2;font-weight:bold;font-size:14px;padding:10px 24px;border-radius:5px;text-decoration:none;font-family:Arial,sans-serif;mso-padding-alt:10px 24px;">Share the signup link</a>
<!--[if mso]>
</td></tr></table>
<![endif]-->
</div>
<!--[if mso]>
</td></tr></table>
<![endif]-->
</td></tr>
<tr><td style="padding:0 0 16px;text-align:center;">
<p style="font-size:12px;color:#999;margin:0 0 4px;font-family:Arial,sans-serif;">&#169; 2026 DING&#8203;.AI &#183; All rights reserved</p>
<p style="font-size:12px;margin:0;font-family:Arial,sans-serif;"><a href="[UNSUBSCRIBE_URL]" style="color:#999;text-decoration:underline;">Unsubscribe</a></p>
</td></tr>
</table>
</td></tr>
</table></td></tr></table></body></html>

Each [SECTION] block:
<tr><td style="padding:4px 40px 0;"><div style="font-size:20px;font-weight:700;color:#d4622a;margin-bottom:20px;">[EMOJI] [Section Title]</div>
<div style="margin-bottom:26px;">
  <div style="font-size:15px;font-weight:700;color:#1a3a6b;line-height:1.45;margin-bottom:10px;">[Story Headline]</div>
  <p style="font-size:14px;color:#333;line-height:1.75;margin:0 0 8px;">[Summary. <em>([Sources])</em>]</p>
  <p style="font-size:13.5px;color:#8899aa;line-height:1.65;margin:4px 0 0;"><strong style="color:#8899aa;">Why it matters:</strong> [Consequence]</p>
</div>
</td></tr>
<tr><td style="padding:20px 40px 0;"><table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="border-top:1px solid #e8ecf2;font-size:0;line-height:0;">&nbsp;</td></tr></table></td></tr>

[QUICK_HITS] block:
<tr><td style="padding:4px 40px 0;"><div style="font-size:20px;font-weight:700;color:#d4622a;margin-bottom:16px;">&#9889; Quick Hits</div>
<ul style="margin:0;padding:0 0 0 18px;color:#444;font-size:14px;line-height:1.85;">
  <li style="margin-bottom:6px;">[One-sentence hit 1]</li>
  <li style="margin-bottom:6px;">[One-sentence hit 2]</li>
  <li style="margin-bottom:6px;">[One-sentence hit 3]</li>
  <li style="margin-bottom:6px;">[One-sentence hit 4]</li>
  <li style="margin-bottom:0;">[One-sentence hit 5]</li>
</ul></td></tr>
<tr><td style="padding:20px 40px 0;"><table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="border-top:1px solid #e8ecf2;font-size:0;line-height:0;">&nbsp;</td></tr></table></td></tr>

Return ONLY the JSON object. No markdown fences. No explanation outside the JSON."""


def generate_newsletter(claude_client, news_context: str, recent_headlines: list) -> dict:
    """Returns dict with 'subject' and 'html' keys."""
    today_str    = date.today().strftime("%A, %B %d, %Y")
    recent_str   = json.dumps(recent_headlines, indent=2) if recent_headlines else "None — first edition!"
    prompt       = NEWSLETTER_PROMPT.format(
        today=today_str,
        news_context=news_context,
        recent_headlines=recent_str,
    )

    print("🤖 Calling Claude API to generate newsletter…")

    def _call():
        return claude_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8096,
            messages=[{"role": "user", "content": prompt}],
        )

    message = with_retry(_call)
    raw     = message.content[0].text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw   = "\n".join(lines[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.split("\n")[:-1])
    raw = raw.strip()

    try:
        result = json.loads(raw)
        assert "subject" in result and "html" in result
        # Always use a consistent DING! branded subject line
        result["subject"] = f"DING! Your {date.today().strftime('%A')} briefing is here \U0001f5de\ufe0f"
        return result
    except Exception:
        # Fallback: treat the whole thing as HTML with a default subject
        print("  ⚠️  Could not parse JSON response — using raw output as HTML")
        return {
            "subject": f"DING! Your {date.today().strftime('%A')} briefing is here \U0001f5de\ufe0f",
            "html":    raw,
        }


def extract_headlines_from_html(html: str) -> list:
    pattern = r'color:#1a3a6b[^>]*>([^<]{20,})<'
    matches = re.findall(pattern, html)
    return [m.strip() for m in matches if len(m.strip()) > 20][:20]

# ── Plain-text conversion ─────────────────────────────────────────────────────
def html_to_text(html: str) -> str:
    """
    Convert HTML newsletter to a readable plain-text fallback.
    Strips tags, collapses whitespace, and preserves structure with blank lines.
    """
    # Remove <style> and <head> blocks entirely
    text = re.sub(r'<(style|head|script)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Replace structural tags with newlines/dashes
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(p|div|tr|td|li|h[1-6])>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<li[^>]*>', '• ', text, flags=re.IGNORECASE)
    text = re.sub(r'<h[1-6][^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<hr[^>]*>', '\n' + '─' * 40 + '\n', text, flags=re.IGNORECASE)

    # Unwrap <a> tags — keep the URL inline
    text = re.sub(
        r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        lambda m: f"{m.group(2).strip()} ({m.group(1)})" if m.group(1) not in m.group(2) else m.group(2),
        text, flags=re.IGNORECASE | re.DOTALL,
    )

    # Strip remaining tags
    text = re.sub(r'<[^>]+>', '', text)

    # Decode HTML entities
    text = html_lib.unescape(text)

    # Collapse runs of blank lines to at most 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Strip trailing whitespace per line
    lines = [line.rstrip() for line in text.split('\n')]
    text  = '\n'.join(lines).strip()

    return text


def extract_preheader(html: str) -> str:
    """
    Extract the newsletter intro paragraph for use as the email preheader
    (the preview snippet visible in most inbox clients before opening).
    Falls back to a generic string.
    """
    # The intro is in a <p> after "Hi [NAME]!" — look for the first long <p>
    match = re.search(r'<p[^>]*style="font-size:15px[^>]*>(.*?)</p>', html, re.DOTALL | re.IGNORECASE)
    if match:
        snippet = re.sub(r'<[^>]+>', '', match.group(1))
        snippet = html_lib.unescape(snippet).strip()
        # Truncate to ~120 chars for inbox preview
        if len(snippet) > 120:
            snippet = snippet[:117].rsplit(' ', 1)[0] + '…'
        return snippet
    return "Your daily signal-over-noise morning briefing from DING.AI."


def inject_preheader(html: str, preheader: str) -> str:
    """
    Inject an invisible preheader span right after <body> so inbox clients
    show it as the preview text. Pads with whitespace to push body text out.
    """
    padding = '&nbsp;' * 100 + '&#847;' * 100
    snippet = html_lib.escape(preheader)
    preheader_html = (
        f'<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">'
        f'{snippet}{padding}'
        f'</div>\n'
    )
    return html.replace('<body', preheader_html + '<body', 1)


# ── Gmail sending ─────────────────────────────────────────────────────────────
def is_valid_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))


def send_via_gmail(html: str, subject: str, subscribers: list) -> int:
    """Send newsletter to all subscribers via Brevo transactional email API."""
    if not subscribers:
        print("No subscribers to send to.")
        return 0

    brevo_api_key = os.environ.get("BREVO_API_KEY", "")
    if not brevo_api_key:
        print("BREVO_API_KEY not set - aborting send.")
        return 0

    UNSUB_BASE = "https://agarwalsanchit.github.io/ding-ai-newsletter/unsubscribed.html"
    SHARE_URL  = "https://agarwalsanchit.github.io/ding-ai-newsletter/"

    sender_email = os.environ.get("GMAIL_ADDRESS", "sanchitpurdue@gmail.com")
    sent = 0
    failed_emails = []

    for sub in subscribers:
        email = sub.get("email", "").strip()
        name = sub.get("name", "Subscriber").strip() or "Subscriber"
        if not email:
            continue

        unsub_url = f"{UNSUB_BASE}?email={urllib.parse.quote(email)}"

        # Personalise greeting
        html_personalised = html.replace("Hi [NAME]!", f"Hi {name}!")
        # Replace unsubscribe placeholder
        html_personalised = html_personalised.replace("[UNSUBSCRIBE_URL]", unsub_url)

        # Inject preheader
        preheader_text = f"Your daily briefing from DING&#8203;.AI \u2013 {date.today().strftime('%A, %B %d')}"
        preheader_html = (
            f'<div style="display:none;max-height:0;overflow:hidden;">'
            f'{preheader_text}&nbsp;</div>'
        )
        html_personalised = html_personalised.replace("<body>", f"<body>{preheader_html}", 1)

        # Inject share block before </body>

        text_content = (
            f"Hi {name}!\n\nYour DING.AI briefing is ready.\n"
            f"Open the HTML version for the full experience.\n\n"
            f"Share DING.AI: {SHARE_URL}\n\n"
            f"Unsubscribe: {unsub_url}"
        )
        payload = {
            "sender": {"name": "DING.AI", "email": sender_email},
            "to": [{"email": email, "name": name}],
            "subject": subject,
            "htmlContent": html_personalised,
            "textContent": text_content,
            "headers": {
                "List-Unsubscribe": f"<{unsub_url}>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            },
        }
        req = urllib.request.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "api-key": brevo_api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = getattr(resp, "status", resp.getcode())
                if status in (200, 201):
                    print(f"  [OK] Sent to {email}")
                    sent += 1
                else:
                    print(f"  [FAIL] {email}: HTTP {status}")
                    failed_emails.append(email)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:200]
            print(f"  [FAIL] {email}: {exc.code} {body}")
            failed_emails.append(email)
        except Exception as exc:
            print(f"  [FAIL] {email}: {exc}")
            failed_emails.append(email)

    print(f"\nBrevo send complete: {sent} sent, {len(failed_emails)} failed.")
    return sent


def _notify_admin_of_failures(failed_emails: list, subject: str):
    """Send a plain-text failure alert to the newsletter owner."""
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        return
    try:
        msg            = MIMEMultipart("alternative")
        msg["Subject"] = f"[DING.AI] ⚠️ Send failures for: {subject}"
        msg["From"]    = GMAIL_ADDRESS
        msg["To"]      = GMAIL_ADDRESS
        body = (
            f"The following addresses failed during today's send:\n\n"
            + "\n".join(f"  - {e}" for e in failed_emails)
            + "\n\nCheck your Gmail Sent folder for more details."
        )
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, GMAIL_ADDRESS, msg.as_string())
        print("  📧 Failure alert sent to admin.")
    except Exception as e:
        print(f"  (Could not send failure alert: {e})")

# ── Archive publishing ────────────────────────────────────────────────────────
def publish_to_archive(html: str, subject: str):
    """Save today's issue to docs/issues/ and update the JSON index."""
    today_str = date.today().isoformat()
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    # Write the issue HTML
    issue_path = os.path.join(ARCHIVE_DIR, f"{today_str}.html")

    # Wrap with a simple "read online" header bar linking back to archive
    archive_bar = (
        f'<div style="background:#eef1f8;text-align:center;padding:10px;'
        f'font-family:Arial,sans-serif;font-size:12px;color:#888;">'
        f'You\'re reading the DING.AI archive. '
        f'<a href="../index.html" style="color:#2d7dd2;">View all issues</a>'
        f'</div>'
    )
    issue_html = html.replace("</body>", archive_bar + "\n</body>")
    # Replace placeholder unsubscribe URL with generic unsubscribe page in archive copy
    unsub_generic = "https://agarwalsanchit.github.io/ding-ai-newsletter/unsubscribed.html"
    issue_html = re.sub(r'\[UNSUBSCRIBE_URL\]', unsub_generic, issue_html)

    with open(issue_path, "w", encoding="utf-8") as f:
        f.write(issue_html)
    print(f"📰 Archive issue saved → {issue_path}")

    # Update the JSON index
    index: list = []
    if os.path.exists(ARCHIVE_INDEX):
        try:
            with open(ARCHIVE_INDEX) as f:
                index = json.load(f)
        except Exception:
            index = []

    # Remove today's entry if it exists, then prepend
    index = [e for e in index if e.get("date") != today_str]
    index.insert(0, {"date": today_str, "subject": subject})

    # Keep 90 days
    cutoff = (date.today() - timedelta(days=90)).isoformat()
    index  = [e for e in index if e.get("date", "") >= cutoff]

    with open(ARCHIVE_INDEX, "w") as f:
        json.dump(index, f, indent=2)
    print(f"📋 Archive index updated ({len(index)} issues)")


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
    print("📂 Loading headline history…")
    history          = load_history()
    recent_headlines = get_recent_headlines(history)
    print(f"  Found {len(recent_headlines)} recent headlines for deduplication")

    # Step 2: Fetch news
    print("\n🔍 Fetching news via Tavily…")
    articles_by_section: dict = {}
    today_month_year = date.today().strftime("%B %Y")
    for section_name, query in SECTIONS:
        full_query = f"{query} {today_month_year}"
        print(f"  Searching: {section_name}…")
        articles_by_section[section_name] = search_news(tavily_client, full_query)
        print(f"  → {len(articles_by_section[section_name])} articles found")

    news_context = build_news_context(articles_by_section)

    # Step 3: Generate newsletter
    print()
    result  = generate_newsletter(claude_client, news_context, recent_headlines)
    html    = result["html"]
    subject = result["subject"]
    print(f"  Subject: {subject}")
    print(f"  Generated {len(html):,} characters of HTML")

    # Step 4: Save HTML + publish to archive
    os.makedirs("history", exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        f.write(html)
    print(f"💾 HTML saved to {OUTPUT_FILE}")
    publish_to_archive(html, subject)

    # Step 5: Send or draft
    print()
    sent_count = 0
    if SEND_MODE == "send":
        subscribers = load_subscribers()
        if not subscribers:
            print("⚠️  No subscribers found — skipping send.")
        else:
            sent_count = send_via_gmail(html, subject, subscribers)
            print(f"\n✅ Sent to {sent_count}/{len(subscribers)} subscriber(s).")
    else:
        print(f"📝 SEND_MODE=draft — newsletter saved to {OUTPUT_FILE}. Not emailed.")
        print(f"   To send for real, set SEND_MODE=send in GitHub Secrets.")

    # Step 6: Update history
    new_headlines = extract_headlines_from_html(html)
    save_history(history, new_headlines, sent_count=sent_count)

    print(f"\n{'='*60}")
    print(f"  ✅ Done! Mode: {SEND_MODE} | Sent: {sent_count} | Headlines: {len(new_headlines)}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
