"""Live, privacy-conscious fan-reaction summaries for a game.

The worker polls a small sample of recent public X posts and asks Grok for a
short, uncertainty-aware description.  It deliberately does not keep posts or
author information after each summary; the tactile loop never waits on network
requests.
"""

import json
import os
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


X_RECENT_SEARCH_URL = "https://api.x.com/2/tweets/search/recent"
GROK_CHAT_URL = "https://api.x.ai/v1/chat/completions"


@dataclass(frozen=True)
class FanPulse:
    """A spoken-friendly reaction snapshot, or an explanation of no result."""

    text: str
    sampled_posts: int
    updated_at: float
    error: Optional[str] = None


def _json_request(url, *, headers, method="GET", body=None, timeout=12):
    request = Request(url, headers=headers, method=method, data=body)
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"network error: {exc.reason}") from exc


def fetch_recent_posts(query, bearer_token, max_results=30):
    """Fetch a bounded, English-language sample of public posts from X."""
    params = urlencode({
        "query": f"({query}) lang:en -is:retweet",
        "max_results": max(10, min(max_results, 100)),
        "tweet.fields": "created_at,public_metrics",
    })
    payload = _json_request(
        f"{X_RECENT_SEARCH_URL}?{params}",
        headers={"Authorization": f"Bearer {bearer_token}"},
    )
    return [post["text"] for post in payload.get("data", []) if post.get("text")]


def summarize_with_grok(posts, api_key, model="grok-4.7"):
    """Return two concise sentences suited to being read aloud during play."""
    if not posts:
        return "No recent public fan posts matched this game query."

    prompt = (
        "You summarize a small, unrepresentative sample of public fan posts "
        "for a blind sports fan. In at most two short sentences, describe the "
        "dominant emotional tone and one specific game-context theme. Say "
        "'in this sample' or 'some fans' rather than claiming all fans agree. "
        "Do not repeat usernames, slurs, threats, or unverified factual claims. "
        "If the posts are mixed or mostly off-topic, say so plainly.\n\nPosts:\n"
        + "\n".join(f"- {post}" for post in posts)
    )
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": "Be concise, cautious, and accessible."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 100,
    }).encode("utf-8")
    response = _json_request(
        GROK_CHAT_URL,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        body=payload,
    )
    try:
        return response["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, AttributeError) as exc:
        raise RuntimeError("Grok returned no readable summary") from exc


class FanPulseService:
    """Refresh fan context in a daemon thread without interrupting gameplay."""

    def __init__(self, query, interval_seconds=90, on_update: Optional[Callable] = None):
        self.query = query
        self.interval_seconds = interval_seconds
        self.on_update = on_update
        self._latest = FanPulse("Fan pulse is starting…", 0, time.time())
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="fan-pulse", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)

    def latest(self):
        with self._lock:
            return self._latest

    def _publish(self, pulse):
        with self._lock:
            self._latest = pulse
        if self.on_update:
            self.on_update(pulse)

    def _run(self):
        x_token = os.getenv("X_BEARER_TOKEN")
        grok_key = os.getenv("XAI_API_KEY")
        if not x_token or not grok_key:
            self._publish(FanPulse(
                "Fan pulse unavailable: add X_BEARER_TOKEN and XAI_API_KEY.",
                0, time.time(), "missing credentials",
            ))
            return

        while not self._stop.is_set():
            try:
                posts = fetch_recent_posts(self.query, x_token)
                summary = summarize_with_grok(posts, grok_key)
                self._publish(FanPulse(summary, len(posts), time.time()))
            except RuntimeError as exc:
                self._publish(FanPulse(
                    "Fan pulse could not refresh; keeping the game experience moving.",
                    0, time.time(), str(exc),
                ))
            self._stop.wait(self.interval_seconds)
