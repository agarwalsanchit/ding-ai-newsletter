"""
Seed approved_articles with 10 hand-crafted articles for UI development.

article_id is NOT NULL in the schema (FK → articles), so this script first
inserts a minimal placeholder row into articles for each seeded article, then
inserts the approved_articles row pointing at it.

Idempotent: skips any article whose title already exists in approved_articles.
Re-run safely after editing the ARTICLES list below.

Usage:
    python scripts/seed_approved_articles.py
"""
import os
import sys
from datetime import date
from dotenv import load_dotenv
from supabase import create_client

load_dotenv("supabase.env")
load_dotenv()

db = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"],
)

# ── Source ID cache ────────────────────────────────────────────────────────────
# Each placeholder articles row needs a source_id. Look up once per topic.
_source_id_cache: dict = {}

def get_source_id(topic: str) -> str:
    if topic in _source_id_cache:
        return _source_id_cache[topic]
    result = db.table("sources").select("id").eq("topic", topic).execute()
    if not result.data:
        print(f"ERROR: no sources row for topic {topic!r}. Run seed_sources.py first.")
        sys.exit(1)
    _source_id_cache[topic] = result.data[0]["id"]
    return _source_id_cache[topic]


# ── Articles to seed ───────────────────────────────────────────────────────────
# Edit this list freely. Do NOT include: rank_score (generated), article_id (set below).
ARTICLES = [
    {
        "topic":            "🚨 Top News",
        "article_date":     "2026-05-16",
        "title":            "US and China Reach Preliminary Trade Framework After Geneva Talks",
        "balanced_summary": (
            "Senior US and Chinese trade officials concluded two days of talks in Geneva "
            "on Friday, announcing a preliminary framework to reduce tariffs on a range of "
            "consumer goods and resume agricultural exports suspended since 2024. The deal "
            "does not resolve disputes over semiconductor export controls or Chinese EV "
            "subsidies, which both sides described as requiring further negotiation. Treasury "
            "Secretary Scott Bessent called the outcome 'a meaningful first step,' while "
            "Chinese commerce ministry spokesperson He Yongqian said it 'lays groundwork for "
            "stable trade relations.' Markets rallied on the news, with the S&P 500 rising 1.4%."
        ),
        "why_it_matters":   (
            "A partial trade truce reduces near-term inflation pressure on US consumers "
            "and gives global supply chains a window of stability, though unresolved "
            "tech-sector tensions keep the broader trade war very much alive."
        ),
        "score_importance": 5,
        "score_urgency":    5,
        "score_interest":   4,
        "source_urls":      ["https://apnews.com/article/us-china-trade-geneva-2026"],
        "approved_by":      "human",
    },
    {
        "topic":            "🌍 Geopolitics & World Affairs",
        "article_date":     "2026-05-15",
        "title":            "EU Imposes Sanctions on Three Russian Energy Firms Over Ukraine Fuel Exports",
        "balanced_summary": (
            "The European Union approved a new sanctions package Thursday targeting three "
            "Russian state-linked energy companies accused of supplying jet fuel used in "
            "strikes on Ukrainian civilian infrastructure. The measures freeze EU-held assets "
            "and ban dealings by European firms. Russia called the sanctions 'illegal and "
            "counterproductive.' Ukraine's foreign minister Andrii Sybiha welcomed the move "
            "but urged broader action on Russian LNG shipments, which continue to enter "
            "European ports under existing carve-outs. The package passed with 24 of 27 "
            "member states in favour; Hungary, Slovakia, and Austria abstained."
        ),
        "why_it_matters":   (
            "The targeted designations signal the EU is willing to squeeze Russian energy "
            "revenues even at political cost, but the LNG carve-outs show the bloc's "
            "dependence on Russian gas has not fully unwound."
        ),
        "score_importance": 4,
        "score_urgency":    3,
        "score_interest":   4,
        "source_urls":      ["https://reuters.com/article/eu-russia-sanctions-energy-2026"],
        "approved_by":      "human",
    },
    {
        "topic":            "💼 Business & Finance",
        "article_date":     "2026-05-15",
        "title":            "Nvidia Posts Record $44B Revenue Quarter, Driven by Blackwell AI Chip Demand",
        "balanced_summary": (
            "Nvidia reported fiscal Q1 2027 revenue of $44.1 billion on Wednesday, up 69% "
            "year-over-year, surpassing analyst consensus of $43.2 billion. Data center "
            "revenue hit $39.1 billion as hyperscalers continued accelerating Blackwell GPU "
            "deployments for AI training and inference workloads. CEO Jensen Huang said lead "
            "times for Blackwell systems remain 'demand-constrained,' suggesting supply has "
            "not yet caught up. Gaming revenue fell 8% quarter-over-quarter as consumers "
            "held back purchases ahead of a rumoured next-generation GeForce refresh. Shares "
            "rose 6% in after-hours trading."
        ),
        "why_it_matters":   (
            "Nvidia's results confirm that enterprise AI spending is still accelerating "
            "rather than plateauing, with direct implications for cloud providers, AI "
            "startups, and every company benchmarking its own GPU procurement timeline."
        ),
        "score_importance": 4,
        "score_urgency":    4,
        "score_interest":   5,
        "source_urls":      ["https://reuters.com/article/nvidia-earnings-q1-2027-2026"],
        "approved_by":      "human",
    },
    {
        "topic":            "🔬 Science & Technology",
        "article_date":     "2026-05-14",
        "title":            "Google DeepMind Releases AlphaFold 3 API for Non-Commercial Researchers",
        "balanced_summary": (
            "Google DeepMind on Thursday opened public API access to AlphaFold 3, its "
            "protein-and-molecule structure prediction model, for non-commercial academic "
            "use. The release includes support for DNA, RNA, and small-molecule ligand "
            "predictions alongside protein structures — capabilities not available in the "
            "earlier open-weight AlphaFold 2 release. Usage is capped at 1,000 queries per "
            "day per researcher and requires institutional affiliation verification. "
            "DeepMind said commercial licensing terms for pharmaceutical and biotech "
            "companies will be announced separately. The model's accuracy on the CASP15 "
            "benchmark exceeds prior methods by a significant margin on multi-chain "
            "complexes."
        ),
        "why_it_matters":   (
            "Broad access to AlphaFold 3's multi-molecule capabilities accelerates drug "
            "discovery research globally, though the commercial licensing split will "
            "determine whether biotech startups can actually build on it."
        ),
        "score_importance": 4,
        "score_urgency":    3,
        "score_interest":   5,
        "source_urls":      ["https://deepmind.google/alphafold3-api-release-2026"],
        "approved_by":      "human",
    },
    {
        "topic":            "🔬 Science & Technology",
        "article_date":     "2026-05-13",
        "title":            "OpenAI Launches GPT-5 with Extended Reasoning and 1M Token Context Window",
        "balanced_summary": (
            "OpenAI released GPT-5 on Tuesday, its most capable model to date, featuring "
            "a one-million-token context window and a new 'extended thinking' mode that "
            "allows the model to reason through multi-step problems before producing output. "
            "The model is available via API and in ChatGPT Plus, Team, and Enterprise tiers. "
            "OpenAI published an 87-page technical report but did not disclose training data "
            "or parameter count. Early benchmarks from independent researchers show "
            "significant gains on graduate-level STEM tasks and legal reasoning compared to "
            "GPT-4o, though performance on creative writing tasks showed smaller improvements. "
            "Pricing starts at $15 per million input tokens in standard mode."
        ),
        "why_it_matters":   (
            "The one-million-token context and extended reasoning shift what's tractable for "
            "enterprise AI applications, but the pricing and opaque training data will "
            "determine how quickly it displaces existing deployments."
        ),
        "score_importance": 5,
        "score_urgency":    5,
        "score_interest":   5,
        "source_urls":      ["https://openai.com/blog/gpt-5-launch-2026"],
        "approved_by":      "human",
    },
    {
        "topic":            "🎾 Sports & Entertainment",
        "article_date":     "2026-05-15",
        "title":            "Jannik Sinner Wins Italian Open, Extends Clay Court Win Streak to 21 Matches",
        "balanced_summary": (
            "Jannik Sinner defeated Carlos Alcaraz 6-3, 6-7, 6-4 in the Italian Open final "
            "in Rome on Sunday in front of a capacity crowd of 10,500 at Foro Italico. The "
            "victory extended Sinner's clay-court winning streak to 21 matches and marks his "
            "first Rome title. Alcaraz, the defending champion, took the second set in a "
            "tiebreak and appeared to take momentum into the third before Sinner broke "
            "decisively in the ninth game. Both players will next compete at Roland Garros, "
            "which begins May 25. Sinner consolidates his position as world No. 1 with 910 "
            "points added to his ranking."
        ),
        "why_it_matters":   (
            "Sinner's dominance on clay heading into Roland Garros sets up a compelling "
            "rivalry with Alcaraz for the French Open title — the sport's marquee event "
            "of the clay season."
        ),
        "score_importance": 3,
        "score_urgency":    3,
        "score_interest":   5,
        "source_urls":      ["https://apnews.com/article/sinner-alcaraz-rome-final-2026"],
        "approved_by":      "human",
    },
    {
        "topic":            "🏛 Society & Culture",
        "article_date":     "2026-05-14",
        "title":            "US Supreme Court Hears Arguments on Social Media Age Verification Laws",
        "balanced_summary": (
            "The US Supreme Court heard oral arguments Wednesday in NetChoice v. Paxton, a "
            "challenge to Texas and Florida laws requiring age verification before minors "
            "can access social media platforms. Justices across ideological lines pressed "
            "both sides on how to balance First Amendment protections with child safety "
            "concerns. Several justices indicated skepticism toward blanket bans but "
            "appeared more open to narrowly tailored verification requirements. A ruling is "
            "expected by late June. Seventeen other states have passed or are considering "
            "similar legislation; the outcome will effectively set national policy on "
            "minors' social media access."
        ),
        "why_it_matters":   (
            "The ruling will define whether states can enforce age gates on major platforms "
            "or whether First Amendment doctrine blocks such laws — with sweeping "
            "consequences for how teenagers access the internet."
        ),
        "score_importance": 4,
        "score_urgency":    3,
        "score_interest":   4,
        "source_urls":      ["https://apnews.com/article/scotus-social-media-age-verification-2026"],
        "approved_by":      "human",
    },
    {
        "topic":            "🌍 Geopolitics & World Affairs",
        "article_date":     "2026-05-13",
        "title":            "India and Pakistan Agree to Ceasefire After Cross-Border Artillery Exchanges",
        "balanced_summary": (
            "India and Pakistan announced a ceasefire agreement Monday following four days "
            "of artillery exchanges along the Line of Control in Kashmir that killed at "
            "least 14 soldiers on both sides, according to military sources. The agreement "
            "was brokered with UAE mediation and includes provisions for a joint military "
            "hotline review. Both governments described the ceasefire as 'indefinite' but "
            "stopped short of committing to formal peace talks. Pakistani Prime Minister "
            "Shehbaz Sharif called for 'dialogue over escalation'; India's Ministry of "
            "External Affairs said it reserved the right to respond to further 'provocations.' "
            "Civilian evacuations from border villages in Jammu region continued through Monday."
        ),
        "why_it_matters":   (
            "Any armed exchange between two nuclear-armed states carries outsized risk, "
            "and while the ceasefire reduces immediate danger, the underlying dispute over "
            "Kashmir remains unresolved and a flashpoint for future escalation."
        ),
        "score_importance": 5,
        "score_urgency":    4,
        "score_interest":   5,
        "source_urls":      ["https://reuters.com/article/india-pakistan-ceasefire-kashmir-2026"],
        "approved_by":      "human",
    },
    {
        "topic":            "💼 Business & Finance",
        "article_date":     "2026-05-12",
        "title":            "US Inflation Eases to 2.8% in April as Energy and Food Costs Decline",
        "balanced_summary": (
            "The US Bureau of Labor Statistics reported Friday that the Consumer Price Index "
            "rose 2.8% year-over-year in April, down from 3.1% in March and below the 2.9% "
            "consensus forecast. Energy prices fell 1.2% month-over-month as oil markets "
            "stabilised; food-at-home prices declined 0.3% for the second consecutive month. "
            "Core CPI, which strips out food and energy, remained at 3.2%, above the Fed's "
            "2% target. Fed Governor Christopher Waller said the data was 'encouraging' but "
            "insufficient for near-term rate cuts. Markets priced in a 40% probability of a "
            "September cut, up from 28% before the release."
        ),
        "why_it_matters":   (
            "A sustained CPI decline would give the Fed room to cut rates, lowering "
            "borrowing costs for mortgages, business loans, and credit card debt — but "
            "sticky core inflation means that relief may still be months away."
        ),
        "score_importance": 4,
        "score_urgency":    4,
        "score_interest":   4,
        "source_urls":      ["https://apnews.com/article/us-cpi-april-2026-inflation"],
        "approved_by":      "human",
    },
    {
        "topic":            "🚨 Top News",
        "article_date":     "2026-05-12",
        "title":            "WHO Declares Mpox Outbreak in Central Africa a Global Health Emergency",
        "balanced_summary": (
            "The World Health Organization declared a Public Health Emergency of "
            "International Concern on Friday over a rising mpox outbreak centred in the "
            "Democratic Republic of Congo and spreading to four neighbouring countries. "
            "The DRC has reported over 8,400 confirmed cases and 312 deaths in 2026 to "
            "date, driven largely by a new clade Ib strain that appears more transmissible "
            "than prior variants. WHO Director-General Tedros Adhanom Ghebreyesus urged "
            "vaccine manufacturers to accelerate delivery of doses pledged last year, of "
            "which fewer than 20% have been shipped. The European CDC said it was monitoring "
            "the situation but assessed risk to Europe as 'low' given current travel patterns."
        ),
        "why_it_matters":   (
            "A WHO emergency declaration unlocks international funding and coordinates "
            "vaccine supply chains, but with most pledged doses still unshipped, "
            "the gap between declarations and on-the-ground response remains wide."
        ),
        "score_importance": 5,
        "score_urgency":    4,
        "score_interest":   4,
        "source_urls":      ["https://reuters.com/article/who-mpox-emergency-2026"],
        "approved_by":      "human",
    },
]

# ── Insert logic ───────────────────────────────────────────────────────────────
def main():
    # Build set of titles already in approved_articles for idempotency check
    existing = db.table("approved_articles").select("title").execute()
    existing_titles = {row["title"] for row in existing.data}

    inserted = 0
    skipped  = 0

    for art in ARTICLES:
        title = art["title"]

        if title in existing_titles:
            print(f"  SKIP (exists): {title[:70]}")
            skipped += 1
            continue

        # Insert placeholder articles row (required by NOT NULL FK constraint).
        # These rows represent "manually seeded" drafts with no real Tavily data.
        source_id = get_source_id(art["topic"])
        placeholder = db.table("articles").insert({
            "source_id":    source_id,
            "source_urls":  art["source_urls"],
            "topic":        art["topic"],
            "article_date": art["article_date"],
            "status":       "approved",
            # Claude-generated fields are NULL — seeded articles bypass processing.
        }).execute()
        article_id = placeholder.data[0]["id"]

        # Insert the approved_articles row.
        row = {
            "article_id":       article_id,
            "topic":            art["topic"],
            "article_date":     art["article_date"],
            "title":            title,
            "balanced_summary": art["balanced_summary"],
            "why_it_matters":   art["why_it_matters"],
            "score_importance": art["score_importance"],
            "score_urgency":    art["score_urgency"],
            "score_interest":   art["score_interest"],
            "source_urls":      art["source_urls"],
            "approved_at":      art.get("approved_at", date.today().isoformat()),
            "approved_by":      art["approved_by"],
            "published_at":     art.get("approved_at", date.today().isoformat()),
        }
        result = db.table("approved_articles").insert(row).execute()
        new_id = result.data[0]["id"]
        print(f"  INSERT [{new_id[:8]}…] {title[:70]}")
        existing_titles.add(title)
        inserted += 1

    print(f"\nDone: {inserted} inserted, {skipped} skipped.")


if __name__ == "__main__":
    main()
