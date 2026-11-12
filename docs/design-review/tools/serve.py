#!/usr/bin/env python3
"""Read-only static preview of a built snapshot (see build_snapshot.py).

  python3 docs/design-review/tools/serve.py SITE_DIR --port 8411

Serves files like the production Caddy config: directory index.html, and
/404.html with status 404 for anything missing. Never writes.
"""
from __future__ import annotations

import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):  # quiet
        pass

    def send_error(self, code, message=None, explain=None):
        page = Path(self.directory) / "404.html"
        if code == 404 and page.is_file():
            body = page.read_bytes()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
            return
        super().send_error(code, message, explain)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("site", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8411)
    args = parser.parse_args()
    handler = functools.partial(Handler, directory=str(args.site.resolve()))
    Handler.extensions_map = {**Handler.extensions_map, ".webp": "image/webp", ".json": "application/json", ".xml": "application/xml"}
    ThreadingHTTPServer((args.host, args.port), handler).serve_forever()


if __name__ == "__main__":
    main()
