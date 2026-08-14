"""Serve the dashboard: python scripts/serve.py [port] -> http://localhost:8877/dashboard/"""
import http.server
import os
import sys
from pathlib import Path

os.chdir(Path(__file__).resolve().parent.parent)

# Optional argument so a second session can serve the same tree without fighting over the port.
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8877


class NoCache(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass


print(f"dashboard: http://localhost:{PORT}/dashboard/")
http.server.ThreadingHTTPServer(("127.0.0.1", PORT), NoCache).serve_forever()
