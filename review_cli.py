"""
DING.AI Review CLI — DESIGN.md tasks 2.8, 2.9
Interactive CLI for human review of pending articles and daily brief.

Entry point: python review_cli.py
"""

import json
import os
import sys
from datetime import date, datetime, timezone
from dotenv import load_dotenv
from supabase import create_client

load_dotenv("supabase.env")  # SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
load_dotenv()                # .env

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

REVIEWER = "sanchit"


# ── Display helpers ───────────────────────────────────────────────────────────
def hr(char="─", width=60):
    print(char * width)


def ask_yes_no(prompt: str) -> bool:
    while True:
        ans = input(f"{prompt} [y/n]: ").strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("  Please enter y or n.")


def ask_int(prompt: str, lo: int = 1, hi: int = 5):
    while True:
        raw = input(f"{prompt} [{lo}-{hi}, or Enter to skip]: ").strip()
        if raw == "":
            return None
        try:
            val = int(raw)
            if lo <= val <= hi:
                return val
        except ValueError:
            pass
        print(f"  Enter an integer between {lo} and {hi}, or press Enter to skip.")


# ── Safety gate ───────────────────────────────────────────────────────────────
def run_safety_gate(db, article: dict) -> None:
    """Show article details, ask 5 yes/no checks, approve or reject."""
    article_id = article["id"]
    hr("═")
    print(f"ARTICLE REVIEW")
    hr("═")
    print(f"Topic:      {article.get('topic', 'N/A')}")
    print(f"Title:      {article.get('title', 'N/A')}")
    print()
    urls = article.get("source_urls") or []
    for u in urls:
        print(f"  Source: {u}")
    print()
    print("Summary:")
    print(f"  {article.get('balanced_summary', 'N/A')}")
    print()
    print("Why it matters:")
    print(f"  {article.get('why_it_matters', 'N/A')}")
    print()
    print("AI Scores:")
    print(f"  Importance : {article.get('score_importance', 'N/A')} / 5")
    print(f"  Urgency    : {article.get('score_urgency', 'N/A')} / 5")
    print(f"  Interest   : {article.get('score_interest', 'N/A')} / 5")
    print()
    print("AI Confidence:")
    print(f"  Factual    : {article.get('ai_confidence_factual', 'N/A')} / 5")
    print(f"  On-topic   : {article.get('ai_confidence_on_topic', 'N/A')} / 5")
    print(f"  Source     : {article.get('ai_confidence_source', 'N/A')} / 5")
    hr()

    print("Safety Gate — answer 5 questions:\n")
    checks = {}
    checks["factual"]       = ask_yes_no("1. Factually accurate? (no hallucinations)")
    checks["on_topic"]      = ask_yes_no("2. On-topic for its category?")
    checks["source_credible"] = ask_yes_no("3. Source credible and verifiable?")
    checks["not_duplicate"] = ask_yes_no("4. Not a duplicate of recent coverage?")
    checks["safe_to_publish"] = ask_yes_no("5. Safe to publish? (no harmful/biased framing)")

    all_yes = all(checks.values())
    decision = "approved" if all_yes else "rejected"
    now_iso  = datetime.now(timezone.utc).isoformat()

    if all_yes:
        # Fetch article_date and other fields needed for approved_articles
        try:
            row_data = (
                db.table("articles")
                .select("article_date, topic, title, article_brief, balanced_summary, detail_summary, why_it_matters, "
                        "score_importance, score_urgency, score_interest, source_urls")
                .eq("id", article_id)
                .execute()
            )
            a_row = row_data.data[0] if row_data.data else {}
        except Exception as exc:
            print(f"  Warning: could not fetch article fields: {exc}")
            a_row = {}

        approved_row = {
            "article_id":      article_id,
            "topic":           a_row.get("topic", article.get("topic")),
            "article_date":    a_row.get("article_date", date.today().isoformat()),
            "title":           a_row.get("title", article.get("title")),
            "article_brief":   a_row.get("article_brief"),
            "balanced_summary": a_row.get("balanced_summary", article.get("balanced_summary")),
            "detail_summary":  a_row.get("detail_summary"),
            "why_it_matters":  a_row.get("why_it_matters", article.get("why_it_matters")),
            "score_importance": a_row.get("score_importance", article.get("score_importance")),
            "score_urgency":    a_row.get("score_urgency", article.get("score_urgency")),
            "score_interest":   a_row.get("score_interest", article.get("score_interest")),
            "source_urls":      a_row.get("source_urls", article.get("source_urls", [])),
            "approved_by":      "human",
            "approved_at":      now_iso,
        }
        try:
            db.table("approved_articles").insert(approved_row).execute()
        except Exception as exc:
            print(f"  Warning: failed to insert approved_articles: {exc}")

        try:
            db.table("articles").update({
                "status":      "approved",
                "reviewed_at": now_iso,
            }).eq("id", article_id).execute()
        except Exception as exc:
            print(f"  Warning: failed to update articles.status: {exc}")

        print("\n  APPROVED.")
    else:
        try:
            db.table("articles").update({
                "status":      "rejected",
                "reviewed_at": now_iso,
            }).eq("id", article_id).execute()
        except Exception as exc:
            print(f"  Warning: failed to update articles.status: {exc}")

        failed = [q for q, v in checks.items() if not v]
        print(f"\n  REJECTED. Failed checks: {', '.join(failed)}")

    # Insert human_reviews row
    review_row = {
        "article_id":   article_id,
        "reviewer":     REVIEWER,
        "mode":         "safety_gate",
        "decision":     decision,
        "check_results": checks,
    }
    try:
        db.table("human_reviews").insert(review_row).execute()
    except Exception as exc:
        print(f"  Warning: failed to insert human_reviews: {exc}")


# ── Calibration ───────────────────────────────────────────────────────────────
def run_calibration(db, article: dict) -> None:
    """Show AI scores, ask human to confirm or override."""
    article_id = article["id"]
    hr()
    print("CALIBRATION — AI scores vs. your judgment")
    print(f"  Title: {article.get('title', 'N/A')}")
    print(f"  AI: Importance={article.get('score_importance')}, "
          f"Urgency={article.get('score_urgency')}, "
          f"Interest={article.get('score_interest')}")
    print()
    print("Override scores? (press Enter to accept AI score)")

    imp_human     = ask_int("  Importance (1-5)")
    urg_human     = ask_int("  Urgency (1-5)")
    int_human     = ask_int("  Interest (1-5)")
    any_override  = any(v is not None for v in [imp_human, urg_human, int_human])

    if not any_override:
        print("  No overrides — AI scores accepted.")
        return

    note = input("  Calibration note (optional): ").strip() or None

    # Update approved_articles scores if this article was approved
    try:
        approved = (
            db.table("approved_articles")
            .select("id")
            .eq("article_id", article_id)
            .execute()
        )
        if approved.data:
            approved_id = approved.data[0]["id"]
            score_update = {}
            if imp_human is not None:
                score_update["score_importance"] = imp_human
            if urg_human is not None:
                score_update["score_urgency"] = urg_human
            if int_human is not None:
                score_update["score_interest"] = int_human
            if score_update:
                db.table("approved_articles").update(score_update).eq("id", approved_id).execute()
                print(f"  Updated approved_articles scores: {score_update}")
    except Exception as exc:
        print(f"  Warning: failed to update approved_articles scores: {exc}")

    # Insert calibration human_reviews row
    review_row = {
        "article_id":            article_id,
        "reviewer":              REVIEWER,
        "mode":                  "calibration",
        "decision":              "no_change",
        "check_results":         None,
        "score_importance_human": imp_human,
        "score_urgency_human":   urg_human,
        "score_interest_human":  int_human,
        "calibration_note":      note,
    }
    # Remove None-valued optional fields
    review_row = {k: v for k, v in review_row.items() if v is not None}
    try:
        db.table("human_reviews").insert(review_row).execute()
        print("  Calibration saved.")
    except Exception as exc:
        print(f"  Warning: failed to insert calibration human_reviews: {exc}")


# ── Brief review ──────────────────────────────────────────────────────────────
def run_brief_review(db, today_str: str) -> None:
    """Review today's daily brief if it exists and hasn't been approved yet."""
    try:
        result = (
            db.table("daily_briefs")
            .select("*")
            .eq("brief_date", today_str)
            .is_("approved_at", "null")
            .execute()
        )
    except Exception as exc:
        print(f"  Could not fetch daily brief: {exc}")
        return

    if not result.data:
        print("  No pending brief found for today.")
        return

    brief = result.data[0]
    brief_id = brief.get("id")

    hr("═")
    print("DAILY BRIEF REVIEW")
    hr("═")
    print(f"  Editorial opener : {brief.get('editorial_opener', 'N/A')}")
    print(f"  Brief body       :")
    print(f"    {brief.get('brief_body', 'N/A')}")
    print(f"  Transition line  : {brief.get('transition_line', 'N/A')}")
    chips = brief.get("topic_chips") or []
    print(f"  Topic chips      : {', '.join(chips)}")
    print(f"  AI confidence    : {brief.get('ai_confidence', 'N/A')} / 5")
    hr()

    ok = ask_yes_no(
        "Does the brief accurately represent today's deck without overstating, "
        "missing the lede, or editorializing beyond the articles?"
    )

    now_iso = datetime.now(timezone.utc).isoformat()

    if ok:
        try:
            db.table("daily_briefs").update({
                "approved_at": now_iso,
                "approved_by": "human",
            }).eq("id", brief_id).execute()
            print("  Brief approved.")
        except Exception as exc:
            print(f"  Warning: failed to approve brief: {exc}")
    else:
        feedback = input("  What's wrong with the brief? (leave blank to skip): ").strip()
        print(f"  Brief NOT approved. Feedback: {feedback or '(none)'}")
        print("  Brief left with approved_at=NULL for regeneration.")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set.")
        sys.exit(1)

    db = create_client(SUPABASE_URL, SUPABASE_KEY)
    today_str = date.today().isoformat()

    print(f"\n{'='*60}")
    print(f"  DING.AI Review CLI — {today_str}")
    print(f"{'='*60}\n")

    # Fetch pending articles for today
    try:
        pending = (
            db.table("articles")
            .select("*")
            .eq("status", "pending")
            .eq("article_date", today_str)
            .not_.is_("processed_at", "null")
            .execute()
        )
        articles = pending.data
    except Exception as exc:
        print(f"Failed to fetch pending articles: {exc}")
        sys.exit(1)

    if not articles:
        print(f"No pending articles for {today_str}.")
    else:
        print(f"Found {len(articles)} pending article(s) for {today_str}.\n")

        for i, article in enumerate(articles, 1):
            print(f"\n[{i}/{len(articles)}]", end="")
            run_safety_gate(db, article)

        # Calibration mode
        hr()
        if ask_yes_no("\nEnter calibration mode? (review AI scores vs. your judgment)"):
            try:
                approved_arts = (
                    db.table("articles")
                    .select("*")
                    .in_("status", ["approved", "auto_approved"])
                    .eq("article_date", today_str)
                    .execute()
                )
                all_approved = approved_arts.data
            except Exception as exc:
                print(f"  Could not fetch approved articles: {exc}")
                all_approved = []

            # Exclude articles already calibrated this session or in a prior session
            try:
                already = (
                    db.table("human_reviews")
                    .select("article_id")
                    .eq("reviewer", REVIEWER)
                    .eq("mode", "calibration")
                    .execute()
                )
                calibrated_ids = {r["article_id"] for r in already.data}
            except Exception as exc:
                print(f"  Warning: could not fetch prior calibrations: {exc}")
                calibrated_ids = set()

            calibrate_list = [a for a in all_approved if a["id"] not in calibrated_ids]

            if not calibrate_list:
                print("  No new articles to calibrate.")
            else:
                print(f"  {len(calibrate_list)} article(s) to calibrate "
                      f"({len(all_approved) - len(calibrate_list)} already done).")
                for i, article in enumerate(calibrate_list, 1):
                    print(f"\n[{i}/{len(calibrate_list)}]", end="")
                    run_calibration(db, article)

    # Brief review
    hr()
    print("\nChecking for daily brief to review…")
    run_brief_review(db, today_str)

    print(f"\n{'='*60}")
    print(f"  Review session complete.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
