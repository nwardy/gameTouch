"""On-demand, privacy-conscious fan-reaction summaries for a game.

A tactile-board button (or the ``F`` development key) requests one small
sample of recent public X posts. Grok turns it into a concise, uncertainty-aware
description and an intensity score. The tactile/video loop never waits on the
network request and posts are discarded after the response is created.
"""

import json
import os
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi


GROK_RESPONSES_URL = "https://api.x.ai/v1/responses"


def load_local_env(path=".env"):
    """Load the local Grok key without overwriting a real environment variable."""
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        key, separator, value = line.partition("=")
        if separator and key == "XAI_API_KEY" and not os.getenv(key):
            os.environ[key] = value.strip().strip('"').strip("'")


@dataclass(frozen=True)
class FanPulse:
    """A spoken-friendly reaction snapshot, or an explanation of no result."""

    text: str
    sampled_posts: int
    updated_at: float
    intensity: Optional[int] = None
    level: Optional[str] = None
    game_context: Optional[str] = None
    event: Optional[str] = None
    event_confidence: Optional[str] = None
    error: Optional[str] = None


def _json_request(url, *, headers, method="GET", body=None, timeout=45):
    request = Request(url, headers=headers, method=method, data=body)
    try:
        # Python.org's macOS build may not have a system CA bundle configured.
        # certifi supplies a maintained bundle while preserving HTTPS validation.
        context = ssl.create_default_context(cafile=certifi.where())
        with urlopen(request, timeout=timeout, context=context) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"network error: {exc.reason}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise RuntimeError(
            "Grok X Search took longer than 45 seconds. Try the button again in a moment."
        ) from exc


def search_x_with_grok(query, api_key, model="grok-4.7"):
    """Use Grok's live X and web search for one accessible game snapshot."""
    prompt = (
        f"Find the current live context for this game: {query}. "
        "You are assisting a blind sports fan who pressed a button because they "
        "want quick orientation. First use web search for current game state only "
        "when a reliable live-score source is available. Then use X Search for "
        "recent crowd reaction. Return quickly: do not make repeated searches or "
        "deep analysis. The game_context must say 'Live game context unavailable' "
        "if reliable current information is not found. The summary must describe "
        "only the crowd reaction. Do not repeat usernames, slurs, threats, or "
        "unverified factual claims. Do not claim the result represents all fans. "
        "If posts are mixed or off-topic, say that plainly. Set event to a soccer "
        "event only when reliable live web context explicitly supports it; otherwise "
        "set event to none and confidence to low."
    )
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summary": {"type": "string"},
            "intensity": {"type": "integer", "minimum": 0, "maximum": 100},
            "level": {"type": "string", "enum": ["quiet", "building", "high", "urgent"]},
            "game_context": {"type": "string"},
            "event": {"type": "string", "enum": [
                "none", "goal", "yellow_card", "red_card", "offside", "penalty_awarded",
                "corner_kick", "substitution", "var_review",
            ]},
            "event_confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        },
        "required": ["summary", "intensity", "level", "game_context", "event", "event_confidence"],
    }
    payload = json.dumps({
        "model": model,
        "reasoning": {"effort": "low"},
        "input": prompt,
        "tools": [{"type": "web_search"}, {"type": "x_search"}],
        "text": {"format": {
            "type": "json_schema", "name": "fan_pulse", "strict": True, "schema": schema,
        }},
    }).encode("utf-8")
    response = _json_request(
        GROK_RESPONSES_URL,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        body=payload,
    )
    try:
        output_text = response.get("output_text")
        if not output_text:
            output_text = next(
                content["text"]
                for item in response.get("output", [])
                for content in item.get("content", [])
                if content.get("type") == "output_text" and content.get("text")
            )
        result = json.loads(output_text)
        intensity = max(0, min(100, int(result["intensity"])))
        level = str(result["level"]).lower()
        if level not in {"quiet", "building", "high", "urgent"}:
            level = _level_for(intensity)
        summary = str(result["summary"]).strip()
        if not summary:
            raise ValueError("empty summary")
        game_context = str(result["game_context"]).strip()
        if not game_context:
            game_context = "Live game context unavailable."
        event = str(result["event"]).lower()
        if event not in {"none", "goal", "yellow_card", "red_card", "offside", "penalty_awarded", "corner_kick", "substitution", "var_review"}:
            event = "none"
        event_confidence = str(result["event_confidence"]).lower()
        if event_confidence not in {"low", "medium", "high"}:
            event_confidence = "low"
        usage = response.get("usage", {}).get("server_side_tool_usage_details", {})
        sampled_posts = max(0, int(usage.get("x_posts_fetched", 0)))
        web_searches = max(0, int(usage.get("web_search_calls", 0)))
        return {
            "summary": summary[:420], "intensity": intensity, "level": level,
            "game_context": game_context[:280], "sampled_posts": sampled_posts,
            "web_searches": web_searches, "event": event, "event_confidence": event_confidence,
        }
    except (KeyError, IndexError, StopIteration, AttributeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("Grok returned no readable fan-pulse result") from exc


def _level_for(intensity):
    if intensity >= 75:
        return "urgent"
    if intensity >= 50:
        return "high"
    if intensity >= 25:
        return "building"
    return "quiet"


class FanPulseService:
    """Run one fan-context request at a time without interrupting gameplay."""

    def __init__(self, query, interval_seconds=90, on_update: Optional[Callable] = None):
        self.query = query
        self.interval_seconds = interval_seconds
        self.on_update = on_update
        self._latest = FanPulse("Press F or the fan button to ask what fans are saying.", 0, time.time())
        self._lock = threading.Lock()
        self._thread = None

    def start(self):
        """Retained for the playback lifecycle; requests begin only on trigger."""

    def request_refresh(self):
        """Start one request. Returns False while a prior request is in flight."""
        if self._thread is not None and self._thread.is_alive():
            return False
        self._publish(FanPulse("Checking a recent sample of fan posts…", 0, time.time()))
        self._thread = threading.Thread(target=self._run_once, name="fan-pulse", daemon=True)
        self._thread.start()
        return True

    def stop(self):
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

    def _run_once(self):
        grok_key = os.getenv("XAI_API_KEY")
        if not grok_key:
            self._publish(FanPulse(
                "Fan pulse unavailable: add XAI_API_KEY.",
                0, time.time(), error="missing credentials",
            ))
            return

        try:
            result = search_x_with_grok(self.query, grok_key)
            self._publish(FanPulse(
                result["summary"], result["sampled_posts"], time.time(), result["intensity"],
                result["level"], result["game_context"], result["event"], result["event_confidence"],
            ))
        except RuntimeError as exc:
            self._publish(FanPulse(
                "Fan pulse could not refresh; the game experience is still running.",
                0, time.time(), error=str(exc),
            ))
