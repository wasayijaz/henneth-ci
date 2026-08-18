"""Serve the dashboard: python scripts/serve.py [port] -> http://localhost:8877/dashboard/"""
import http.server
import os
import re
import sys
from pathlib import Path

os.chdir(Path(__file__).resolve().parent.parent)

# Optional argument so a second session can serve the same tree without fighting over the port.
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8877


class NoCache(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        # Keep local preview behaviour aligned with the production shell rewrites:
        # clean dashboard routes are served by dashboard/index.html, while real
        # assets and state files continue through SimpleHTTPRequestHandler.
        clean = path.split("?", 1)[0].strip("/")
        if not clean.startswith("dashboard/"):
            dashboard_asset = Path("dashboard", clean)
            if dashboard_asset.is_file():
                return str(dashboard_asset.resolve())
        route = clean[len("dashboard/"):].strip("/") if clean.startswith("dashboard/") else clean
        if route:
            if route and "." not in route and (
                route in {
                    "today", "board", "watchlist", "portfolio", "settings", "practice",
                    "strategies", "value", "screener", "compare", "scenarios", "research",
                    "sectors", "leaderboard", "news", "macro", "dividends", "calendar", "astro",
                    "market", "tools", "ask", "learn", "plans", "cast", "mychart", "glossary",
                    "shipped", "unsubscribe"
                }
                or re.fullmatch(r"ticker/[^/]+", route)
                or re.fullmatch(r"legal/[^/]+", route)
            ):
                return str(Path("dashboard/index.html").resolve())
        return super().translate_path(path)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass


print(f"dashboard: http://localhost:{PORT}/dashboard/")
http.server.ThreadingHTTPServer(("127.0.0.1", PORT), NoCache).serve_forever()
