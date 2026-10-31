#!/usr/bin/env python3
"""Serve Sajawandi full-page PNGs with CORS for Flutter web Image.network."""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEFAULT_DIR = Path(
    r"C:\Users\Khaled\AndroidStudioProjects\WaqfWIbtida"
    r"\waqf-ibtida-web\public\data\pdf_pages\sajawandi"
)


class CorsHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Cache-Control", "public, max-age=3600")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
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
