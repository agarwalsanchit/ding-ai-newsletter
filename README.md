# DING.AI Newsletter — Cloud Pipeline

Fully automated daily newsletter. Runs on GitHub's servers at 7 AM every day.
**Your Mac does not need to be on.**

## Architecture

```
GitHub Actions (cron 7 AM)
  → Tavily API       — searches the web for today's news (free, 1000 req/month)
  → Claude API       — researches, writes, and formats the HTML newsletter
  → Beehiiv API      — sends to all subscribers (free up to 2,500 subscribers)
  → Git commit       — saves headline history back to this repo for deduplication
```

---

## One-Time Setup (≈ 20 minutes)

### Step 1 — Get API Keys

**A. Anthropic API Key** (you already have this)
- Go to [platform.anthropic.com](https://platform.anthropic.com) → API Keys
- Copy your key

**B. Tavily API Key** (free)
- Sign up at [app.tavily.com](https://app.tavily.com)
- Free tier: 1,000 searches/month (plenty — we use ~6/day)
- Copy your API key from the dashboard

**C. Beehiiv Account + API Key** (free up to 2,500 subscribers)
1. Sign up at [beehiiv.com](https://www.beehiiv.com)
2. Create a new publication — call it "DING.AI" or whatever you like
3. Go to **Settings → Publication** and copy your **Publication ID** (looks like `pub_xxxxxxxx`)
4. Go to **Settings → API** and generate a new API key
5. Copy both the API key and publication ID

### Step 2 — Create the GitHub Repository

```bash
# In your terminal, from the newsletter-cloud folder:
git init
git add .
git commit -m "feat: initial DING.AI newsletter pipeline"

# Create a new PRIVATE repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/ding-ai-newsletter.git
git push -u origin main
```

Or use GitHub Desktop / the GitHub website to create the repo and upload these files.

### Step 3 — Add GitHub Secrets

In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**

Add these 5 secrets:

| Secret Name              | Value                                      |
|--------------------------|--------------------------------------------|
| `ANTHROPIC_API_KEY`      | Your Anthropic API key                     |
| `TAVILY_API_KEY`         | Your Tavily API key                        |
| `BEEHIIV_API_KEY`        | Your Beehiiv API key                       |
| `BEEHIIV_PUBLICATION_ID` | Your Beehiiv publication ID (pub_xxxxxxxx) |
| `SEND_MODE`              | `draft` (change to `send` when ready)      |

### Step 4 — Test with a Manual Run

1. Go to your repo on GitHub → **Actions** tab
2. Click **DING.AI Daily Newsletter** → **Run workflow**
3. Set `send_mode` to `draft` for your first test
4. Watch the logs — it takes about 60-90 seconds
5. Check your Beehiiv dashboard → **Posts** to see the draft

### Step 5 — Go Live

Once you're happy with a few draft runs:
1. Go to GitHub → **Settings → Secrets** → update `SEND_MODE` to `send`
2. The next scheduled run at 7 AM will send to all your Beehiiv subscribers automatically

---

## Adding Subscribers

Share your Beehiiv subscribe page with anyone you want to subscribe.
Find it at: **Beehiiv dashboard → Grow → Subscribe Page**

Beehiiv handles:
- Double opt-in confirmation emails
- Unsubscribe links in every email (legally required)
- Subscriber analytics

You never need to manually edit a list.

---

## Changing the Send Time

Edit `.github/workflows/newsletter.yml` and change the cron expression:

```yaml
- cron: "0 12 * * *"   # 12:00 UTC = 7:00 AM EST / 8:00 AM EDT
```

[Cron expression generator →](https://crontab.guru)

Common times (all UTC):
- 6 AM EST  = `0 11 * * *`
- 7 AM EST  = `0 12 * * *`
- 8 AM EST  = `0 13 * * *`
- 6 AM PST  = `0 14 * * *`

---

## Editor Overrides — Steering the News

You can tell the pipeline to cover specific topics or include specific articles
(with fact-checking) in the next edition. This is an **Overrides** tab in the
same Google Sheet as your subscribers.

### Sheet setup (one-time)

1. Open the same Google Sheet used for subscribers.
2. Add a new tab called **Overrides** with these columns (exact names, first row):
   - `Topic` — e.g. "IPL 2026 playoffs"
   - `URL` — optional, a specific article to include
   - `Strength` — `hard` (must include) or `soft` (nudge)
   - `Section` — optional, e.g. `🎾 Sports & Entertainment`
   - `Run Date` — optional `YYYY-MM-DD`; blank = active every run until you clear the row
   - `Notes` — optional free-text hint (e.g. "focus on KKR's qualifier chances")
3. **File → Share → Publish to web** → pick the **Overrides** tab → **Comma-separated values (.csv)** → Publish. Copy the URL.
4. Add a new GitHub Secret: `OVERRIDES_SHEET_URL` = that CSV link.

A sample is at `docs/overrides_tab_template.csv`.

### How it behaves

- **Hard + Topic** → dedicated Tavily search on the topic; one item guaranteed in the newsletter, bypasses the 7-day dedup.
- **Hard + URL** → the article is fetched, Claude extracts 3–5 key factual claims, each claim is cross-referenced against Tavily, and the rendered item includes a short "Fact check:" line summarizing what's corroborated.
- **Soft + Topic** → added as a hint; included only if substantive news turns up.

Leave the tab empty for business as usual. To pull an item after the run, just
delete the row (or set `Run Date` to a past date).

---

## Checking Run Logs

GitHub → **Actions** tab → click any run → expand the `Run newsletter engine` step.

The bot also commits the updated history file after each run, so you can see a full log of past editions in `history/newsletter_history.json`.

---

## Cost Summary

| Service        | Free Tier                   | When you'd pay              |
|----------------|-----------------------------|-----------------------------|
| GitHub Actions | 2,000 min/month (we use ~2) | Never for this use case     |
| Tavily         | 1,000 searches/month        | $30/month after that        |
| Claude API     | Pay per use                 | ~$0.05–0.15 per newsletter  |
| Beehiiv        | Free up to 2,500 subs       | $49/month after 2,500 subs  |

**Estimated monthly cost at launch: ~$1.50–4.50** (Claude API only)
