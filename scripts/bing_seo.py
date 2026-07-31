"""Bing Webmaster Tools API — submit URLs/sitemaps for henneth.app without the browser UI.
Usage:
  python scripts/bing_seo.py submit-url https://henneth.app/blog/psx-t1-settlement-explained/
  python scripts/bing_seo.py submit-sitemap https://henneth.app/sitemap-index.xml
  python scripts/bing_seo.py sites
Reads BING_WEBMASTER_API_KEY from .env (repo root) or the environment.
"""
import sys
from pathlib import Path

import requests

SITE_URL = "https://www.henneth.app/"  # must match Bing's registered site exactly (GetUserSites)
API_BASE = "https://ssl.bing.com/webmaster/api.svc/json"
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_api_key() -> str:
    import os

    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("BING_WEBMASTER_API_KEY="):
                return line.split("=", 1)[1].strip()
    key = os.environ.get("BING_WEBMASTER_API_KEY")
    if not key:
        raise SystemExit("BING_WEBMASTER_API_KEY not found in .env or environment")
    return key


def submit_url(url: str) -> None:
    key = load_api_key()
    r = requests.post(
        f"{API_BASE}/SubmitUrl?apikey={key}",
        json={"siteUrl": SITE_URL, "url": url},
        timeout=15,
    )
    print(r.status_code, r.text or "(ok, empty response is normal)")


def submit_sitemap(sitemap_url: str) -> None:
    key = load_api_key()
    r = requests.post(
        f"{API_BASE}/SubmitFeed?apikey={key}",
        json={"siteUrl": SITE_URL, "feedUrl": sitemap_url},
        timeout=15,
    )
    print(r.status_code, r.text or "(ok, empty response is normal)")


def list_sites() -> None:
    key = load_api_key()
    r = requests.get(f"{API_BASE}/GetUserSites?apikey={key}", timeout=15)
    print(r.status_code, r.text)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cmd = sys.argv[1]
    if cmd == "submit-url" and len(sys.argv) == 3:
        submit_url(sys.argv[2])
    elif cmd == "submit-sitemap" and len(sys.argv) == 3:
        submit_sitemap(sys.argv[2])
    elif cmd == "sites":
        list_sites()
    else:
        raise SystemExit(__doc__)
