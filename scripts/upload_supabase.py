"""Push the state layer to Supabase Storage (public bucket 'desk') so the Vercel
dashboard can read it. Runs at the end of the cloud pipeline (GitHub Actions).

Env required:
  SUPABASE_URL          e.g. https://qteoncckohuoatbjjykb.supabase.co
  SUPABASE_SERVICE_KEY  service_role key (SECRET — set as a GitHub Actions secret)

Uploads all top-level state/*.json every run (small, changes each cycle) plus
state/intraday/*.json (1D charts). With --deep it also uploads the big per-ticker
history_deep/ and history/ dirs (change ~daily) — the workflow does that on the
first run of the day only, to keep 30-min runs fast.

Free-tier friendly: overwrites in place (x-upsert), JSON only, <1GB bucket."""
import os
import sys

import requests

from psx_data import STATE

URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
BUCKET = os.environ.get("SUPABASE_BUCKET", "desk")


def upload(rel_path: str, data: bytes, sess: requests.Session) -> bool:
    dest = f"{URL}/storage/v1/object/{BUCKET}/{rel_path}"
    r = sess.post(dest, data=data, headers={
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json",
        "x-upsert": "true",
    }, timeout=30)
    return r.status_code in (200, 201)


def gather(deep: bool):
    files = sorted(STATE.glob("*.json"))
    files += sorted((STATE / "intraday").glob("*.json"))
    if deep:
        files += sorted((STATE / "history_deep").glob("*.json"))
        files += sorted((STATE / "history").glob("*.json"))
    return files


def main():
    if not URL or not KEY:
        print("FATAL: set SUPABASE_URL and SUPABASE_SERVICE_KEY", file=sys.stderr)
        sys.exit(1)
    deep = "--deep" in sys.argv
    sess = requests.Session()
    files = gather(deep)
    ok, failed = 0, []
    for f in files:
        rel = f.relative_to(STATE).as_posix()  # e.g. quant.json, intraday/HUBC.json
        try:
            if upload(rel, f.read_bytes(), sess):
                ok += 1
            else:
                failed.append(rel)
        except requests.RequestException as e:
            failed.append(f"{rel}:{str(e)[:40]}")
    print(f"supabase upload: {ok} ok, {len(failed)} failed{' (deep)' if deep else ''}")
    if failed:
        for x in failed[:10]:
            print("  fail:", x)
        sys.exit(1)


if __name__ == "__main__":
    main()
