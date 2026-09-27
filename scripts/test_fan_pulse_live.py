#!/usr/bin/env python3
"""Run one real X -> Grok fan-pulse check without video or hardware.

Example:
    X_BEARER_TOKEN="..." XAI_API_KEY="..." \
      ./.venv/bin/python scripts/test_fan_pulse_live.py --query "#GTvsUGA"
"""

import argparse
import os
import sys

from pathlib import Path

# Running this file directly puts scripts/ on sys.path, not the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fan_pulse import fetch_recent_posts, summarize_with_grok


def main():
    parser = argparse.ArgumentParser(
        description="Fetch a small, current X-post sample and summarize it with Grok."
    )
    parser.add_argument("--query", required=True, help="X search query, such as '#GTvsUGA'")
    parser.add_argument("--max-posts", type=int, default=20, help="X posts to sample (10 to 100)")
    args = parser.parse_args()

    x_token = os.getenv("X_BEARER_TOKEN")
    grok_key = os.getenv("XAI_API_KEY")
    if not x_token or not grok_key:
        sys.exit("Set X_BEARER_TOKEN and XAI_API_KEY in this terminal before running the live test.")

    print(f"Fetching up to {max(10, min(args.max_posts, 100))} recent X posts for: {args.query}")
    try:
        posts = fetch_recent_posts(args.query, x_token, max_results=args.max_posts)
        print(f"Sampled {len(posts)} post(s). Asking Grok for a cautious fan-pulse summary…\n")
        print(summarize_with_grok(posts, grok_key))
    except RuntimeError as error:
        sys.exit(f"Live fan-pulse test failed: {error}")


if __name__ == "__main__":
    main()
