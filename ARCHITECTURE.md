# DING.AI Newsletter — Architecture

## Data Sources

News is fetched exclusively via the **Tavily Search API** (`search_depth="advanced"`, `days=2`, `topic="news"`). Six predefined queries are run each day:

| Section | Query focus |
|---|---|
| Top News | Breaking news, restricted to reuters.com, apnews.com, bbc.com |
| Geopolitics & World Affairs | International conflict, diplomacy |
| Business & Finance | Stock market, economy, earnings |
| Science & Technology | AI, research, innovation |
| Sports & Entertainment | Major game results, celebrity news |
| Society & Culture | Politics, social trends, education |

Each query returns up to 6 article snippets (title, 400-char excerpt, URL, publish date). There are no RSS feeds, scrapers, or other API sources.

## Fetch Mechanism

`newsletter.py` is the single entry-point script. It runs inside **GitHub Actions** on a cron schedule (`0 15 * * *` — 8:00 AM PDT / 15:00 UTC) on an `ubuntu-latest` runner. It can also be triggered manually from the Actions tab with a `send_mode` input. Before the main script runs, `sync_subscribers.py` fetches the latest subscriber list from two Google Sheets CSV exports (signup form + unsubscribe form). The entire pipeline finishes in roughly 60–90 seconds and requires no local machine.

## AI Processing

Claude (`claude-sonnet-4-6`) is called **once per run** via the Anthropic Python SDK (`newsletter.py:279–286`). The prompt (`NEWSLETTER_PROMPT`, lines 171–264) provides:

- Today's date
- All fetched article snippets, grouped by section
- Headlines from the past 3 days (loaded from `history/newsletter_history.json`) to avoid duplicating recent stories

Claude is instructed to write 2–3 stories per section (punchy headline, 2–3 sentence summary, "Why it matters" line), an intro paragraph, and 5 "Quick Hits" bullets. It must return a **JSON object** with two keys: `"subject"` (email subject line) and `"html"` (a complete inline-styled HTML email built from a rigid table-based template embedded in the prompt). If JSON parsing fails, the raw text is used as the HTML body.

## Storage

All storage is **flat files committed back to the Git repository** after each run:

| Path | Contents |
|---|---|
| `history/today_newsletter.html` | Latest generated HTML (overwritten daily) |
| `history/newsletter_history.json` | Rolling 7-day log of sent headlines + send counts (used for deduplication) |
| `subscribers.json` | Active subscriber list (name + email), synced from Google Sheets before each run |
| `docs/issues/YYYY-MM-DD.html` | Per-issue archive pages, kept 90 days |
| `docs/issues/index.json` | JSON index of the last 90 issues (date + subject) |

There is no database.

## Publishing

Two destinations:

1. **Email** — sent individually to each subscriber in `subscribers.json` via the **Brevo transactional email API** (`/v3/smtp/email`). Each email is personalized (name, unsubscribe link). On send failures, an admin alert is sent to the owner's Gmail via SMTP. The `SEND_MODE` secret controls whether emails go out (`send`) or are only saved locally (`draft`).

2. **Web archive** — the `docs/` folder is served as a **GitHub Pages** site. Each issue is saved as a standalone HTML page; `docs/index.html` links to the archive. The site also hosts the signup page and an unsubscribe confirmation page.

## Open Questions

- **README is outdated.** It describes Beehiiv as the email sender, but the actual code uses Brevo. Beehiiv secrets (`BEEHIIV_API_KEY`, `BEEHIIV_PUBLICATION_ID`) appear nowhere in `newsletter.py` or the workflow.
- **`send_via_gmail` is a misleading function name** (`newsletter.py:422`) — it sends via Brevo's REST API, not Gmail. Gmail is only used for admin failure alerts.
- **`yo@woo.com`** appears in `subscribers.json` and looks like a test address that was never removed.
- **Unsubscribe flow is incomplete in production.** Clicking "Unsubscribe" in an email links to a static GitHub Pages page. Whether that page actually writes to the Google Sheet (so `sync_subscribers.py` can remove the address) depends on a Google Form or script wired to the sheet — that integration is not in this repository.
- **`manage_subscribers.py`** is a local CLI tool for manually adding/removing subscribers. It is not called by the GitHub Actions workflow; changes made with it would be overwritten on the next run when `sync_subscribers.py` merges from the Google Sheet.
