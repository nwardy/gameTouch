#!/usr/bin/env python3
"""Small local control server for the synchronized replay demo.

Run this on the presentation laptop. The web page schedules its two video
panels against the timestamp returned by ``/api/playback/start``. A Jetson on
the same network can poll ``/api/playback/status`` via jetson_demo_client.py.
No video analysis happens here: this is intentionally a replay coordinator.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import shutil
import time
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parent
WEB_ROOT = PROJECT_ROOT / "web"
DEFAULT_COUNTDOWN_SECONDS = 5.0
playback_state = {"run_id": 0, "start_at": None, "countdown_seconds": 5.0}


class DemoRequestHandler(SimpleHTTPRequestHandler):
    """Serve the page, known media files, and the tiny sync API."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_GET(self):  # noqa: N802 - standard library callback name
        path = urlparse(self.path).path
        if path == "/api/playback/status":
            return self._json(playback_state)
        if path.startswith("/media/"):
            return self._serve_media(path.removeprefix("/media/"))
        return super().do_GET()

    def do_POST(self):  # noqa: N802 - standard library callback name
        path = urlparse(self.path).path
        if path != "/api/playback/start":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(content_length) if content_length else b"{}"
            request = json.loads(raw)
            countdown = float(request.get("countdown_seconds", DEFAULT_COUNTDOWN_SECONDS))
        except (ValueError, json.JSONDecodeError):
            self.send_error(HTTPStatus.BAD_REQUEST, "Expected JSON countdown_seconds")
            return

        # Keep the timing window sensible. This is a demo countdown, not a
        # precise distributed-clock protocol.
        countdown = min(max(countdown, 1.0), 10.0)
        playback_state["run_id"] += 1
        playback_state["start_at"] = time.time() + countdown
        playback_state["countdown_seconds"] = countdown
        self._json(playback_state)

    def _serve_media(self, relative_path: str):
        candidate = (PROJECT_ROOT / relative_path).resolve()
        if PROJECT_ROOT not in candidate.parents or not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        # Keep media outside the public web directory while still allowing the
        # supplied demo clips to play in a normal HTML video element.
        content_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(candidate.stat().st_size))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with candidate.open("rb") as media_file:
            shutil.copyfileobj(media_file, self.wfile)

    def _json(self, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description="Synchronized replay demo server")
    parser.add_argument("--host", default="0.0.0.0", help="network interface to bind")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DemoRequestHandler)
    print(f"Demo control room: http://localhost:{args.port}")
    print("Jetson client: python3 jetson_demo_client.py --server http://<laptop-ip>:8000 ...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping demo server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
