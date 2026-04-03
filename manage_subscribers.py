"""
manage_subscribers.py — DING.AI Subscriber Management CLI

Usage:
    python manage_subscribers.py list              # Show all active subscribers
    python manage_subscribers.py add <email> [name]
    python manage_subscribers.py remove <email>
    python manage_subscribers.py stats            # Subscriber + issue stats

All changes are written to subscribers.json.
"""

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

SUBSCRIBERS_FILE = "subscribers.json"
HISTORY_FILE     = "history/newsletter_history.json"
ARCHIVE_INDEX    = "docs/issues/index.json"


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_valid_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))


def load_subscribers() -> list:
    if not Path(SUBSCRIBERS_FILE).exists():
        return []
    with open(SUBSCRIBERS_FILE) as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print(f"❌ Could not parse {SUBSCRIBERS_FILE}")
            sys.exit(1)

    # Normalise to list-of-dicts
    result = []
    for s in data:
        if isinstance(s, str) and "@" in s:
            result.append({"name": s.split("@")[0].capitalize(), "email": s.strip().lower()})
        elif isinstance(s, dict) and "@" in s.get("email", ""):
            result.append({
                "name":  s.get("name", "Reader"),
                "email": s["email"].strip().lower(),
            })
    return result


def save_subscribers(subs: list):
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(subs, f, indent=2)


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_list(subs: list):
    if not subs:
        print("📭 No subscribers yet.")
        return
    print(f"\n{'#':>4}  {'Name':<20}  Email")
    print("─" * 55)
    for i, s in enumerate(subs, 1):
        print(f"{i:>4}  {s['name']:<20}  {s['email']}")
    print(f"\nTotal: {len(subs)} subscriber(s)\n")


def cmd_add(subs: list, email: str, name: str = ""):
    email = email.strip().lower()
    if not is_valid_email(email):
        print(f"❌ Invalid email address: {email}")
        sys.exit(1)

    existing = [s for s in subs if s["email"] == email]
    if existing:
        print(f"⚠️  {email} is already subscribed (as '{existing[0]['name']}').")
        return subs

    if not name:
        name = email.split("@")[0].capitalize()

    subs.append({"name": name, "email": email})
    save_subscribers(subs)
    print(f"✅ Added: {name} <{email}>")
    return subs


def cmd_remove(subs: list, email: str):
    email   = email.strip().lower()
    before  = len(subs)
    subs    = [s for s in subs if s["email"] != email]
    if len(subs) == before:
        print(f"⚠️  {email} not found in subscriber list.")
    else:
        save_subscribers(subs)
        print(f"✅ Removed: {email}")
    return subs


def cmd_stats(subs: list):
    print("\n── DING.AI Subscriber Stats ──────────────────────────")
    print(f"  Active subscribers : {len(subs)}")

    # Issue count from archive index
    if Path(ARCHIVE_INDEX).exists():
        with open(ARCHIVE_INDEX) as f:
            try:
                index = json.load(f)
                print(f"  Issues published   : {len(index)}")
                if index:
                    latest = sorted(index, key=lambda x: x.get("date", ""), reverse=True)
                    print(f"  Latest issue       : {latest[0]['date']} — {latest[0].get('subject', '(no subject)')}")
            except Exception:
                pass
    else:
        print("  Issues published   : (archive not found)")

    # Total sends from history
    if Path(HISTORY_FILE).exists():
        with open(HISTORY_FILE) as f:
            try:
                history    = json.load(f)
                total_sent = sum(e.get("sent", 0) for e in history)
                print(f"  Emails sent (7d)   : {total_sent}")
            except Exception:
                pass

    # Domain breakdown
    if subs:
        domains: dict = {}
        for s in subs:
            domain = s["email"].split("@")[-1]
            domains[domain] = domains.get(domain, 0) + 1
        print("\n  Domain breakdown:")
        for domain, count in sorted(domains.items(), key=lambda x: -x[1]):
            bar = "█" * count
            print(f"    {domain:<30} {bar} ({count})")

    print()


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main():
    subs = load_subscribers()

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "list":
        cmd_list(subs)

    elif cmd == "add":
        if len(sys.argv) < 3:
            print("Usage: python manage_subscribers.py add <email> [name]")
            sys.exit(1)
        email = sys.argv[2]
        name  = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
        cmd_add(subs, email, name)

    elif cmd == "remove":
        if len(sys.argv) < 3:
            print("Usage: python manage_subscribers.py remove <email>")
            sys.exit(1)
        cmd_remove(subs, sys.argv[2])

    elif cmd == "stats":
        cmd_stats(subs)

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
