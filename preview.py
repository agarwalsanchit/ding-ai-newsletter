"""
preview.py — Local newsletter preview generator
Runs newsletter.py in draft mode and opens the HTML in your browser.
No emails are sent. Requires the same env vars as newsletter.py except Gmail ones.

Usage:
    export ANTHROPIC_API_KEY=...
    export TAVILY_API_KEY=...
    python preview.py
"""

import os
import subprocess
import sys
import webbrowser
from pathlib import Path

OUTPUT_FILE = "history/today_newsletter.html"

def main():
    # Force draft mode
    env = {**os.environ, "SEND_MODE": "draft"}

    print("🔍 Generating newsletter preview (no emails will be sent)…\n")
    result = subprocess.run(
        [sys.executable, "newsletter.py"],
        env=env,
    )

    if result.returncode != 0:
        print("\n❌ newsletter.py exited with an error — check the output above.")
        sys.exit(1)

    html_path = Path(OUTPUT_FILE).resolve()
    if not html_path.exists():
        print(f"\n❌ Output file not found at {html_path}")
        sys.exit(1)

    print(f"\n✅ Preview saved to {html_path}")
    print("🌐 Opening in your browser…")
    webbrowser.open(html_path.as_uri())

if __name__ == "__main__":
    main()
