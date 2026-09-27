#!/usr/bin/env python3
"""Run one real Grok X Search fan-pulse check without video or hardware.

Example:
    ./.venv/bin/python scripts/test_fan_pulse_live.py --query "#GTvsUGA"
"""

import argparse
import os
import sys

from pathlib import Path

# Running this file directly puts scripts/ on sys.path, not the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fan_pulse import load_local_env, search_x_with_grok


def main():
    load_local_env(Path(__file__).resolve().parents[1] / ".env")
    parser = argparse.ArgumentParser(
        description="Use Grok X Search to summarize current fan reaction."
    )
    parser.add_argument("--query", required=True, help="X search query, such as '#GTvsUGA'")
    args = parser.parse_args()

    grok_key = os.getenv("XAI_API_KEY")
    if not grok_key:
        sys.exit("Set XAI_API_KEY in .env before running the live test.")

    print(f"Asking Grok X Search about: {args.query}")
    try:
        result = search_x_with_grok(args.query, grok_key)
        print(f"Used {result['web_searches']} live web search(es) and sampled {result['sampled_posts']} X post(s).\n")
        print(f"Live game context: {result['game_context']}")
        print(f"Soccer event: {result['event'].replace('_', ' ')} ({result['event_confidence']} confidence)")
        print(f"Fan intensity: {result['intensity']}/100 ({result['level']})")
        print(result["summary"])
    except RuntimeError as error:
        sys.exit(f"Live fan-pulse test failed: {error}")


if __name__ == "__main__":
    main()
