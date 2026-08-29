"""Serve the dashboard: python scripts/serve.py [port] -> http://localhost:8877/dashboard/"""
import http.server
import os
import re
import sys
import urllib.parse
from pathlib import Path

os.chdir(Path(__file__).resolve().parent.parent)

# Optional argument so a second session can serve the same tree without fighting over the port.
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8877


class NoCache(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        # Keep local preview behaviour aligned with the production shell rewrites:
        # clean dashboard routes are served by dashboard/index.html, while real
        # assets and state files continue through SimpleHTTPRequestHandler.
        # Decode and normalise BEFORE anything below inspects the path. The parent
        # SimpleHTTPRequestHandler unquotes and drops "."/".." segments itself, so a guard
        # that reads the raw wire path is checking a different string from the one that
        # eventually gets opened: "/%63onfig/desk.json", "/Config/desk.json" (NTFS is
        # case-insensitive) and "/../config/desk.json" all walked straight past the deny.
        raw = path.split("?", 1)[0].split("#", 1)[0]
        segments = [
            part
            for part in urllib.parse.unquote(raw).replace("\\", "/").split("/")
            if part and part not in (".", "..")
        ]
        clean = "/".join(segments)
        # AGENTS.md guardrail 9: config/desk.json holds the owner's real capital and the
        # Telegram bot token and must never be served. This handler chdirs to the repo root,
        # so without this deny the whole config/ tree (and .env) is readable by any local
        # client at http://127.0.0.1:<port>/config/desk.json.
        # Point at a path that cannot exist so the normal 404 flow (the branded page below)
        # handles it, rather than emitting a second response from inside translate_path.
        if clean.casefold() == ".env" or (segments and segments[0].casefold() in {"config", ".git"}):
            return str(Path(".not-served").resolve())
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

    def send_error(self, code, message=None, explain=None):
        # Mirror Vercel's custom 404 locally so a bad route is still a useful
        # branded screen during dashboard QA instead of the stdlib error page.
        if code == 404:
            page = Path("dashboard/404.html")
            if page.is_file():
                body = page.read_bytes()
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
        super().send_error(code, message, explain)

    def log_message(self, *a):
        pass


print(f"dashboard: http://localhost:{PORT}/dashboard/")
http.server.ThreadingHTTPServer(("127.0.0.1", PORT), NoCache).serve_forever()
