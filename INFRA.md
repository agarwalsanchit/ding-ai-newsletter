## Service accounts

| Service | Account email | Key location | Notes |
| :---- | :---- | :---- | :---- |
| Tavily | Github account- agarwalsanchit@live.com | GitHub Secret TAVILY\_API\_KEY | Active. Second account exists, unused. |
| Anthropic | sanchitpurdue@gmail.com | GitHub Secret ANTHROPIC\_API\_KEY |  |
| Brevo | sanchitpurdue@gmail.com | GitHub Secret BREVO\_API\_KEY |  |
| Vercel    | Github Account   | vercel.com dashboard | Hobby tier (free) |
| Supabase | sanchitpurdue@gmail.com | GitHub Secrets SUPABASE\_URL + SUPABASE\_SERVICE\_ROLE\_KEY; also in supabase.env locally | Free tier. Project: ding-ai-newsletter. Service role key used by pipeline (bypasses RLS). Anon key used by Vercel PWA (subject to RLS). |

## GitHub Secrets

All secrets required by `.github/workflows/newsletter.yml`:

| Secret | Used by | Notes |
| :---- | :---- | :---- |
| ANTHROPIC\_API\_KEY | pipeline.py, newsletter.py | Claude API |
| TAVILY\_API\_KEY | pipeline.py | News search |
| SUPABASE\_URL | pipeline.py, newsletter.py | Supabase project URL |
| SUPABASE\_SERVICE\_ROLE\_KEY | pipeline.py, newsletter.py | Bypasses RLS; never expose to frontend |
| BREVO\_API\_KEY | newsletter.py | Email sending |
| BREVO\_SENDER\_EMAIL | newsletter.py | Must be a Brevo-verified sender (custom domain, not @gmail.com) |
| BREVO\_SENDER\_NAME | newsletter.py | Display name in From line |
| GMAIL\_ADDRESS | newsletter.py | Reply-To + admin failure alerts |
| GMAIL\_APP\_PASSWORD | newsletter.py | Gmail App Password for SMTP failure alerts only |
| SEND\_MODE | newsletter.py | "send" for scheduled daily run; "draft" is the safe default |
| SIGNUP\_SHEET\_URL | sync\_subscribers.py | Google Sheets CSV export of signup form |
| UNSUBSCRIBE\_SHEET\_URL | sync\_subscribers.py | Google Sheets CSV export of unsubscribe form |

## Local dev setup

```bash
cp supabase.env.example supabase.env   # fill in SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
cp .env.example .env                   # fill in ANTHROPIC_API_KEY + TAVILY_API_KEY

python -m venv .venv
source .venv/bin/activate
pip install anthropic tavily-python supabase python-dotenv requests

python pipeline.py      # fetch + AI process → writes to Supabase
# review in real terminal:
.venv/bin/python review_cli.py
python newsletter.py    # render + send (SEND_MODE=draft by default)
```

`.venv/` is gitignored. Never commit it.
