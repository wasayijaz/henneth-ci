"""Serve the dashboard: python scripts/serve.py -> http://localhost:8877/dashboard/"""
import http.server
import os
from pathlib import Path

os.chdir(Path(__file__).resolve().parent.parent)


class NoCache(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass


print("dashboard: http://localhost:8877/dashboard/")
http.server.ThreadingHTTPServer(("127.0.0.1", 8877), NoCache).serve_forever()
