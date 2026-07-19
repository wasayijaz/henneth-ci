"""Web Push sender — watchlist alerts.

INERT UNTIL KEYED. A static host cannot send a push, so this runs from the GitHub Actions
cron or by hand. It reads VAPID keys and Supabase service credentials from ENVIRONMENT
VARIABLES only — nothing is hardcoded and no key is ever written to state/ or logs.

Per CLAUDE.md ("never crash the cycle") every not-configured path prints one clear line and
exits 0. Missing keys, a missing `pywebpush`, or a missing table are all normal off-states,
not failures.

Environment (all required to actually send):
    VAPID_PUBLIC_KEY    base64url public key   (same value the client uses)
    VAPID_PRIVATE_KEY   base64url private key  (SECRET — repo secret only)
    VAPID_SUBJECT       "mailto:you@example.com"
    SUPABASE_URL        https://<project>.supabase.co
    SUPABASE_SERVICE_KEY  service-role key (SECRET — server-side only, bypasses RLS)

Usage:
    python scripts/push_send.py                 # dry run: report config, send nothing
    python scripts/push_send.py --send          # actually deliver queued alerts
    python scripts/push_send.py --send --test <user_id>   # one test push to one user
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from psx_data import STATE, load_json, save_json

TABLE = "push_subscriptions"
ENV_KEYS = ("VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY", "VAPID_SUBJECT",
            "SUPABASE_URL", "SUPABASE_SERVICE_KEY")


def env_config():
    """Return (config_dict, missing_list). Empty strings count as missing."""
    cfg = {k: (os.environ.get(k) or "").strip() for k in ENV_KEYS}
    return cfg, [k for k in ENV_KEYS if not cfg[k]]


def have_pywebpush():
    """Detect the dependency; NEVER install it. Adding an unvetted package to a cron that
    publishes the live site is exactly the kind of silent change this desk doesn't do."""
    try:
        from pywebpush import webpush  # noqa: F401
        return True, None
    except ImportError as e:
        return False, str(e)


def _rest(cfg, method, path, params=None, body=None):
    """Minimal Supabase REST call (no supabase-py dependency — requests-only stack)."""
    url = cfg["SUPABASE_URL"].rstrip("/") + "/rest/v1/" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "apikey": cfg["SUPABASE_SERVICE_KEY"],
        "Authorization": "Bearer " + cfg["SUPABASE_SERVICE_KEY"],
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read().decode() or "[]"
    return json.loads(raw) if raw.strip() else []


def fetch_subscriptions(cfg, user_id=None):
    params = {"select": "id,user_id,endpoint,p256dh,auth"}
    if user_id:
        params["user_id"] = "eq." + user_id
    return _rest(cfg, "GET", TABLE, params=params)


def delete_subscription(cfg, endpoint):
    """404/410 from the push service means the browser is gone for good — drop the row so
    dead endpoints don't accumulate and slow every future run."""
    try:
        _rest(cfg, "DELETE", TABLE, params={"endpoint": "eq." + endpoint})
    except (urllib.error.URLError, ValueError):
        pass


def pending_alerts():
    """Alerts to deliver. state/push_queue.json is written by whatever decides an alert is
    warranted (monitor / signals); absent file = nothing to send, which is today's state.
    Shape: [{ "user_id": "...", "symbol": "LUCK", "title": "...", "body": "..." }, ...]"""
    return load_json(STATE / "push_queue.json", [])


def clear_queue():
    save_json(STATE / "push_queue.json", [])


def deliver(cfg, sub, payload):
    """One push. Returns (ok, gone). `gone` = endpoint permanently dead."""
    from pywebpush import WebPushException, webpush
    try:
        webpush(
            subscription_info={
                "endpoint": sub["endpoint"],
                "keys": {"p256dh": sub.get("p256dh"), "auth": sub.get("auth")},
            },
            data=json.dumps(payload),
            vapid_private_key=cfg["VAPID_PRIVATE_KEY"],
            vapid_claims={"sub": cfg["VAPID_SUBJECT"]},
            timeout=15,
        )
        return True, False
    except WebPushException as e:
        code = getattr(getattr(e, "response", None), "status_code", None)
        return False, code in (404, 410)
    except Exception:  # noqa: BLE001 — a sender fault must never take the cycle down
        return False, False


def main(argv):
    send = "--send" in argv
    test_user = None
    if "--test" in argv:
        i = argv.index("--test")
        test_user = argv[i + 1] if len(argv) > i + 1 else None

    cfg, missing = env_config()
    if missing:
        print("push_send: not configured - missing " + ", ".join(missing) +
              ". Web Push is INERT; nothing sent. See docs/OPERATIONS.md section 11.")
        return 0

    ok, err = have_pywebpush()
    if not ok:
        print("push_send: 'pywebpush' is not installed in this environment (%s). "
              "Not installing it automatically — add it to the workflow deliberately "
              "after review. Nothing sent." % err)
        return 0

    queue = [] if test_user else pending_alerts()
    if test_user:
        queue = [{"user_id": test_user, "symbol": "", "title": "PSX Trade Desk",
                  "body": "Test alert — push is wired up correctly."}]
    if not queue:
        print("push_send: configured, queue empty - nothing to send.")
        return 0

    if not send:
        print("push_send: DRY RUN - configured, %d alert(s) queued. Re-run with --send." % len(queue))
        return 0

    by_user = {}
    for a in queue:
        uid = a.get("user_id")
        if uid:
            by_user.setdefault(uid, []).append(a)

    sent = failed = pruned = 0
    for uid, alerts in by_user.items():
        try:
            subs = fetch_subscriptions(cfg, uid)
        except (urllib.error.URLError, ValueError) as e:
            print("push_send: could not read subscriptions for %s (%s) - skipping." % (uid, str(e)[:100]))
            continue
        for a in alerts:
            payload = {
                "title": a.get("title") or "PSX Trade Desk",
                "body": a.get("body") or "",
                "symbol": (a.get("symbol") or "").upper(),
                "tag": a.get("tag") or "",
            }
            for sub in subs:
                good, gone = deliver(cfg, sub, payload)
                if good:
                    sent += 1
                else:
                    failed += 1
                    if gone:
                        delete_subscription(cfg, sub["endpoint"])
                        pruned += 1

    if not test_user:
        clear_queue()
    print("push_send: %d delivered, %d failed, %d dead endpoint(s) pruned at %s"
          % (sent, failed, pruned, time.strftime("%Y-%m-%d %H:%M:%S")))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as e:  # noqa: BLE001 — Rule: network/runtime failures never crash the cycle
        print("push_send: unexpected error (%s) - exiting cleanly, nothing sent." % str(e)[:200])
        sys.exit(0)
