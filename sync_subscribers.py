"""
sync_subscribers.py
Fetches the Google Sheets CSV export of the sign-up form and writes
a fresh subscribers.json, merging with any manually-added entries.

Run automatically as part of the GitHub Actions newsletter workflow.
"""

import csv
import io
import json
import os
import sys
import urllib.request

SHEET_CSV_URL   = os.environ.get("SIGNUP_SHEET_URL", "")
SUBSCRIBERS_FILE = "subscribers.json"


def fetch_csv(url: str) -> list[dict]:
    """Download the published Google Sheet CSV and return rows as dicts."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        content = resp.read().decode("utf-8-sig")  # strip BOM if present
    reader = csv.DictReader(io.StringIO(content))
    return list(reader)


def find_column(row: dict, candidates: list[str]) -> str:
    """Case-insensitive search for a column name among candidates."""
    for key in row:
        for candidate in candidates:
            if candidate.lower() in key.lower():
                return key
    return ""


def parse_subscribers(rows: list[dict]) -> list[dict]:
    """Extract name + email from CSV rows, handling various column name formats."""
    if not rows:
        return []

    sample = rows[0]
    email_col = find_column(sample, ["email", "e-mail", "mail"])
    name_col  = find_column(sample, ["name", "first name", "full name", "your name"])

    if not email_col:
        print("❌ Could not find an email column in the sheet. Columns found:", list(sample.keys()))
        return []

    print(f"   Email column: '{email_col}'" + (f"  |  Name column: '{name_col}'" if name_col else "  |  No name column"))

    subs = []
    for row in rows:
        email = row.get(email_col, "").strip().lower()
        if not email or "@" not in email:
            continue
        name = row.get(name_col, "").strip() if name_col else ""
        if not name:
            name = email.split("@")[0].replace(".", " ").replace("_", " ").title()
        subs.append({"name": name, "email": email})
    return subs


def load_existing() -> list[dict]:
    """Load current subscribers.json, normalising to list-of-dicts format."""
    if not os.path.exists(SUBSCRIBERS_FILE):
        return []
    try:
        with open(SUBSCRIBERS_FILE) as f:
            data = json.load(f)
        result = []
        for s in data:
            if isinstance(s, str) and "@" in s:
                result.append({"name": s.split("@")[0].title(), "email": s.lower()})
            elif isinstance(s, dict) and "@" in s.get("email", ""):
                result.append({"name": s.get("name", "Reader"), "email": s["email"].lower()})
        return result
    except Exception:
        return []


def merge(sheet_subs: list[dict], existing: list[dict]) -> list[dict]:
    """
    Merge sheet sign-ups with manually-added entries.
    Sheet data takes priority for names; manual entries not in sheet are kept.
    Deduplicates by email.
    """
    by_email = {}
    # Load manual entries first (lower priority)
    for s in existing:
        by_email[s["email"]] = s
    # Sheet entries override manual ones (name from form is authoritative)
    for s in sheet_subs:
        by_email[s["email"]] = s
    return sorted(by_email.values(), key=lambda x: x["email"])


def main():
    SIGNUP_SHEET_URL = SHEET_CSV_URL
    if not SIGNUP_SHEET_URL:
        print("⚠️  SIGNUP_SHEET_URL not set — skipping subscriber sync.")
        sys.exit(0)

    print("📋 Syncing subscribers from Google Sheet...")

    try:
        rows = fetch_csv(SIGNUP_SHEET_URL)
        print(f"   Fetched {len(rows)} row(s) from sheet")
    except Exception as e:
        print(f"❌ Failed to fetch sheet: {e}")
        sys.exit(1)

    sheet_subs = parse_subscribers(rows)
    print(f"   Valid sign-ups in sheet: {len(sheet_subs)}")

    existing = load_existing()
    print(f"   Existing in subscribers.json: {len(existing)}")

    merged = merge(sheet_subs, existing)
    print(f"   Total after merge: {len(merged)}")

    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(merged, f, indent=2)

    print(f"✅ subscribers.json updated with {len(merged)} subscriber(s):")
    for s in merged:
        print(f"   • {s['name']} <{s['email']}>")


if __name__ == "__main__":
    main()
