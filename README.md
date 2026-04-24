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

## Deliverability — DMARC & the Sender Address

**If you set the From address to `something@gmail.com` and send via Brevo, Gmail will spam-folder or reject the email for new subscribers.** Since February 2024, `gmail.com` publishes a strict DMARC policy (`p=reject`) that tells receiving mail servers: "if a message claims to be from @gmail.com but wasn't sent by Google, reject it." Brevo's servers are not Google's, so DMARC fails and the mail is dropped or quarantined. Existing subscribers who have previously engaged with the sender may get grace; brand-new inboxes usually won't.

### The fix

Use a custom domain as the sender:

1. Verify your domain in Brevo: **Senders & IP → Domains → Add a new domain**. Brevo will give you a few DNS records (SPF, DKIM, and DMARC) to add at your registrar.
2. Once verified, add two GitHub secrets:
   - `BREVO_SENDER_EMAIL` → e.g. `newsletter@yourdomain.com`
   - `BREVO_SENDER_NAME` → e.g. `DING.AI`
3. `GMAIL_ADDRESS` is still used as the Reply-To header (so replies still land in your Gmail) and for admin failure alerts.

If `BREVO_SENDER_EMAIL` is missing, the code falls back to `GMAIL_ADDRESS` but prints a loud DMARC warning in the run log.

### Admin failure alerts

When Brevo returns an error for any recipient, the workflow sends a failure summary to `GMAIL_ADDRESS` via Gmail SMTP (using `GMAIL_APP_PASSWORD`). The alert lists each failed address with Brevo's error code/message.

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
