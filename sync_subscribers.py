"""
sync_subscribers.py
Fetches the Google Sheets CSV export of the sign-up form and writes a fresh
subscribers.json, merging with any manually-added entries.
Also reads the unsubscribe sheet and removes any matching emails.
Run automatically as part of the GitHub Actions newsletter workflow.
"""
import csv
import io
import json
import os
import sys
import time
import urllib.request

SHEET_CSV_URL = os.environ.get("SIGNUP_SHEET_URL", "")
UNSUBSCRIBE_SHEET_URL = os.environ.get("UNSUBSCRIBE_SHEET_URL", "")
SUBSCRIBERS_FILE = "subscribers.json"


def _cache_bust(url: str) -> str:
    """Append a timestamp query param so Google's CDN can't serve a stale CSV.

    The ?output=csv publish endpoint caches aggressively; adding a fresh query
    string forces a miss and returns the live sheet contents.
    """
    if not url:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}_ts={int(time.time())}"


def fetch_csv(url: str) -> list[dict]:
    url = _cache_bust(url)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent":    "Mozilla/5.0",
            "Cache-Control": "no-cache",
            "Pragma":        "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        content = resp.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))
        return list(reader)

def find_column(row: dict, candidates: list[str]) -> str:
    for key in row:
        for candidate in candidates:
            if candidate.lower() in key.lower():
                return key
    return ""

def parse_subscribers(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    sample = rows[0]
    email_col = find_column(sample, ["email", "e-mail", "mail"])
    name_col = find_column(sample, ["name", "first name", "full name", "your name"])
    if not email_col:
        print("Could not find an email column in the sheet. Columns found:", list(sample.keys()))
        return []
    print(f"  Email column: '{email_col}'" + (f" | Name column: '{name_col}'" if name_col else " | No name column"))
    subs = []
    dropped = 0
    for idx, row in enumerate(rows, 1):
        email = row.get(email_col, "").strip().lower()
        if not email or "@" not in email:
            dropped += 1
            print(f"    ✗ Row {idx}: dropped (invalid or empty email '{email}')")
            continue
        name = row.get(name_col, "").strip() if name_col else ""
        if not name:
            name = email.split("@")[0].replace(".", " ").replace("_", " ").title()
        subs.append({"name": name, "email": email})
    if dropped:
        print(f"  Dropped {dropped} row(s) with invalid/missing email")
    return subs

def parse_unsubscribes(rows: list[dict]) -> set:
    if not rows:
        return set()
    sample = rows[0]
    email_col = find_column(sample, ["email", "e-mail", "mail"])
    if not email_col:
        print("Could not find email column in unsubscribe sheet. Columns:", list(sample.keys()))
        return set()
    print(f"  Unsubscribe email column: '{email_col}'")
    return {
        row.get(email_col, "").strip().lower()
        for row in rows
        if row.get(email_col, "").strip()
    }

def apply_unsubscribes(subscribers: list[dict], unsub_emails: set) -> list[dict]:
    if not unsub_emails:
        return subscribers
    filtered = [s for s in subscribers if s["email"] not in unsub_emails]
    removed = len(subscribers) - len(filtered)
    if removed:
        print(f"  Removed {removed} unsubscribed address(es).")
    return filtered

def load_existing() -> list[dict]:
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
    by_email = {}
    for s in existing:
        by_email[s["email"]] = s
    for s in sheet_subs:
        by_email[s["email"]] = s
    return sorted(by_email.values(), key=lambda x: x["email"])

def main():
    SIGNUP_SHEET_URL = SHEET_CSV_URL
    if not SIGNUP_SHEET_URL:
        print("SIGNUP_SHEET_URL not set -- skipping subscriber sync.")
        sys.exit(0)
    print("Syncing subscribers from Google Sheet...")
    try:
        rows = fetch_csv(SIGNUP_SHEET_URL)
        print(f"  Fetched {len(rows)} row(s) from sheet")
    except Exception as e:
        print(f"Failed to fetch sheet: {e}")
        sys.exit(1)
    sheet_subs = parse_subscribers(rows)
    print(f"  Valid sign-ups in sheet: {len(sheet_subs)}")
    existing = load_existing()
    print(f"  Existing in subscribers.json: {len(existing)}")
    merged = merge(sheet_subs, existing)
    print(f"  Total after merge: {len(merged)}")
    if UNSUBSCRIBE_SHEET_URL:
        print("\nChecking unsubscribe requests...")
        try:
            unsub_rows = fetch_csv(UNSUBSCRIBE_SHEET_URL)
            print(f"  Fetched {len(unsub_rows)} unsubscribe request(s)")
            unsub_emails = parse_unsubscribes(unsub_rows)
            print(f"  Unique unsubscribe emails: {len(unsub_emails)}")
            merged = apply_unsubscribes(merged, unsub_emails)
        except Exception as e:
            print(f"Failed to fetch unsubscribe sheet: {e}")
    else:
        print("UNSUBSCRIBE_SHEET_URL not set -- skipping unsubscribe processing.")
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(merged, f, indent=2)
    print(f"\nsubscribers.json updated with {len(merged)} subscriber(s):")
    for s in merged:
        print(f"  - {s['name']} <{s['email']}>")

if __name__ == "__main__":
    main()
