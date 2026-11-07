#!/usr/bin/env python3
"""Serve Sajawandi full-page PNGs with CORS and persist flagged waqfs for Flutter web."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEFAULT_DIR = Path(
    r"C:\Users\Khaled\AndroidStudioProjects\WaqfWIbtida"
    r"\waqf-ibtida-web\public\data\pdf_pages\sajawandi"
)
FLAGGED_JSON_PATH = Path(__file__).resolve().parent.parent / "data" / "flagged_waqfs.json"


def _read_flagged_state() -> dict:
    if FLAGGED_JSON_PATH.is_file():
        try:
            return json.loads(FLAGGED_JSON_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "sentToReview": [],
        "favorites": [],
        "verified": [],
        "flaggedDetails": {},
        "updatedAt": None,
    }


def _write_flagged_state(payload: dict) -> dict:
    existing = _read_flagged_state()
    sent = sorted(set(payload.get("sentToReview", existing.get("sentToReview", []))))
    favs = sorted(set(payload.get("favorites", existing.get("favorites", []))))
    ver = sorted(set(payload.get("verified", existing.get("verified", []))))
    details = dict(existing.get("flaggedDetails") or {})
    if isinstance(payload.get("flaggedDetails"), dict):
        details.update(payload["flaggedDetails"])
    active_ids = set(sent) | set(favs) | set(ver)
    details = {k: v for k, v in details.items() if k in active_ids}
    state = {
        "sentToReview": sent,
        "favorites": favs,
        "verified": ver,
        "flaggedDetails": details,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    FLAGGED_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    FLAGGED_JSON_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return state


class CorsHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "public, max-age=3600")
        else:
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?")[0] == "/api/review-state":
            data = json.dumps(_read_flagged_state(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if self.path.split("?")[0] == "/api/review-state":
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                payload = {}
            saved = _write_flagged_state(payload if isinstance(payload, dict) else {})
            data = json.dumps(saved, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, fmt: str, *args) -> None:
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--dir", type=str, default=str(DEFAULT_DIR))
    args = parser.parse_args()
    root = Path(args.dir)
    if not root.is_dir():
        raise SystemExit(f"Missing pages dir: {root}")
    handler = partial(CorsHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"Serving {root} on http://127.0.0.1:{args.port}/ (CORS *)")
    server.serve_forever()


if __name__ == "__main__":
    main()
