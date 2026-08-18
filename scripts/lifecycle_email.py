"""Lifecycle email sender — welcome / nudge / activated / digest.

INERT UNTIL KEYED. Mirrors scripts/push_send.py: reads Supabase + Resend credentials from
ENVIRONMENT VARIABLES only, nothing hardcoded, nothing written to state/ or logs. Per CLAUDE.md
("never crash the cycle") every not-configured or unexpected-error path prints one line and
exits 0.

Environment (all required to actually send):
    SUPABASE_URL          https://<project>.supabase.co
    SUPABASE_SERVICE_KEY  server-side secret key (SECRET — bypasses RLS, never ships to a client)
    RESEND_API_KEY        Resend API key (SECRET)

    ^^ SUPABASE_SERVICE_KEY MUST be a new-style `sb_secret_...` key — see push_send.py's docstring
    for why (this project has legacy JWT keys disabled).

Sends from "Henneth <desk@send.henneth.app>" (domain must be verified in Resend), reply-to
hello@henneth.app. Plain urllib for both APIs — no `resend` SDK, deps stay requests/pandas/numpy.

Due windows (all against `lifecycle_queue`, a service-role-only view joining auth.users.email
onto profiles — see docs/lifecycle_email.sql):
    welcome        immediate on first run after signup, on/after LIFECYCLE_EPOCH
    nudge_24h      24h <= age <= 72h, not activated
    activated      on activated_at (any time after)
    nudge_7d       7d <= age <= 14d, not activated
    digest_<ISOyear>-W<week>   activated, digest_prefs.enabled, >=7d since signup,
                                 hash(user_id) % 5 == today's weekday (0=Mon..4=Fri)

LIFECYCLE_EPOCH is a hard floor — without it, the first run ever sees every existing user as
"due for welcome" and blasts the whole base in one run. Never remove it; only move it forward
if intentionally re-basing.

Resend free tier: 3,000/month, 100/day. DAILY_CAP/MONTHLY_CAP below stay under those with margin
(a re-run same day should never trip the platform's own 100/day wall). time.sleep between sends
avoids bursting the API.

Usage:
    python scripts/lifecycle_email.py                       # dry run: report what's due, send nothing
    python scripts/lifecycle_email.py --send                 # actually send what's due
    python scripts/lifecycle_email.py --send --test <user_id> --only welcome   # one test email
    python scripts/lifecycle_email.py --send --only nudge_24h                 # restrict to one key
    python scripts/lifecycle_email.py --send --requeue-stale   # force-retry stuck/failed rows
                                                               # (never resends a 'sent' one)
"""
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from psx_data import STATE, load_json
from email_templates import base
from email_copy import BODIES

ENV_KEYS = ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "RESEND_API_KEY")
FROM_ADDR = "Henneth <desk@send.henneth.app>"
REPLY_TO = "hello@henneth.app"
APP_URL = "https://desk.henneth.app"

# First run floor — any signup before this is treated as already onboarded, never blasted.
LIFECYCLE_EPOCH = dt.datetime(2026, 8, 1, tzinfo=dt.timezone.utc)

DAILY_CAP = 90
MONTHLY_CAP = 2800
SEND_DELAY_SEC = 0.6

DIGEST_WATCHLIST_CAP = 15

# How stale a 'queued' log row must be before it is treated as orphaned rather than in-flight.
RETRY_AFTER = dt.timedelta(hours=6)

# PSX ticker shape. Every one of the 575 symbols in state/universe.json matches this. Used to
# validate user-supplied watchlist entries before they touch the filesystem or an email body.
SYMBOL_RE = re.compile(r"[A-Z0-9]{1,12}")


def env_config():
    cfg = {k: (os.environ.get(k) or "").strip() for k in ENV_KEYS}
    return cfg, [k for k in ENV_KEYS if not cfg[k]]


def _rest(cfg, method, path, params=None, body=None):
    url = cfg["SUPABASE_URL"].rstrip("/") + "/rest/v1/" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    headers = {
        "apikey": cfg["SUPABASE_SERVICE_KEY"],
        "Authorization": "Bearer " + cfg["SUPABASE_SERVICE_KEY"],
        "Content-Type": "application/json",
    }
    if method in ("POST", "PATCH"):
        headers["Prefer"] = "return=representation"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read().decode() or "[]"
    return json.loads(raw) if raw.strip() else []


def fetch_monthly_sent_count(cfg, now):
    """Exact count of rows sent so far this calendar month — the MONTHLY_CAP guard.
    Uses PostgREST's count=exact Prefer header rather than pulling every row."""
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    url = (cfg["SUPABASE_URL"].rstrip("/") + "/rest/v1/lifecycle_email_log?" +
           urllib.parse.urlencode({"select": "id", "status": "eq.sent",
                                    "created_at": "gte." + month_start}))
    headers = {
        "apikey": cfg["SUPABASE_SERVICE_KEY"],
        "Authorization": "Bearer " + cfg["SUPABASE_SERVICE_KEY"],
        "Prefer": "count=exact",
        "Range": "0-0",
    }
    req = urllib.request.Request(url, method="GET", headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        content_range = r.headers.get("Content-Range", "*/0")
    total = content_range.split("/")[-1]
    return int(total) if total.isdigit() else 0


def fetch_queue(cfg, user_id=None):
    params = {"select": "user_id,email,signup_at,activated_at,activation_type,"
                         "email_optout,unsub_token,digest_prefs"}
    if user_id:
        params["user_id"] = "eq." + user_id
    return _rest(cfg, "GET", "lifecycle_queue", params=params)


def fetch_log_rows(cfg, user_ids):
    """Existing log rows keyed by (user_id, email_key) — the idempotency read before computing due.

    Returns the whole row, not just the key, because "a row exists" is NOT the same as "already
    sent": a transient Resend 5xx leaves status='failed', and a process killed mid-send leaves
    status='queued' forever. Keying suppression on mere existence meant either of those silently
    cost the user that email for good."""
    if not user_ids:
        return {}
    params = {"select": "id,user_id,email_key,status,created_at",
              "user_id": "in.(" + ",".join(user_ids) + ")"}
    rows = _rest(cfg, "GET", "lifecycle_email_log", params=params)
    return {(r["user_id"], r["email_key"]): r for r in rows}


def retryable(log_row, now, force=False):
    """May this existing log row be re-claimed and sent again?

    'sent' and 'bounced' are final by definition, and stay final even under force — no operator
    flag may resend an email the user already received. 'failed_final' is how a retry that failed
    AGAIN is marked: that second terminal status bounds automatic retries at exactly one per key
    without needing an attempts column (i.e. without a migration against the live table), so a
    permanently broken row burns one extra send, once, and never again.

    A 'queued' row is only re-claimed after RETRY_AFTER: the sender finishes a row in seconds, so
    a queued row hours old is definitively orphaned, whereas one seconds old may be a concurrent
    run mid-send and re-claiming it would double-send. Unknown status → never retry.

    force (--requeue-stale) is the manual override for a stuck backlog: it drops the age gate and
    re-opens 'failed_final'. It does NOT widen what counts as unsent."""
    status = (log_row.get("status") or "").lower()
    if status == "failed":
        return True
    if status == "failed_final":
        return force
    if status == "queued":
        if force:
            return True
        created = _parse_ts(log_row.get("created_at"))
        return created is not None and (now - created) >= RETRY_AFTER
    return False


def reserve_log_row(cfg, user_id, email_key):
    """Insert first, send second. A 409 (unique violation) means another run already claimed
    this (user_id, email_key) — skip, don't send twice. Returns the inserted row's id, or None
    if already claimed."""
    try:
        rows = _rest(cfg, "POST", "lifecycle_email_log",
                     body={"user_id": user_id, "email_key": email_key, "status": "queued"})
        return rows[0]["id"] if rows else None
    except urllib.error.HTTPError as e:
        if e.code == 409:
            return None
        raise


def claim_log_row(cfg, row_id):
    """Re-claim an existing log row for a retry by flipping it back to 'queued'. Returns False if
    the PATCH failed — the caller must then skip, because sending without a claimed row is exactly
    how a concurrent run double-sends."""
    try:
        _rest(cfg, "PATCH", "lifecycle_email_log", params={"id": "eq." + row_id},
              body={"status": "queued"})
        return True
    except (urllib.error.URLError, ValueError):
        return False


def update_log_row(cfg, row_id, status, resend_id=None):
    body = {"status": status}
    if resend_id:
        body["resend_id"] = resend_id
    try:
        _rest(cfg, "PATCH", "lifecycle_email_log", params={"id": "eq." + row_id}, body=body)
    except (urllib.error.URLError, ValueError):
        pass


def set_optout(cfg, user_id):
    try:
        _rest(cfg, "PATCH", "profiles", params={"id": "eq." + user_id},
              body={"email_optout": True})
    except (urllib.error.URLError, ValueError):
        pass


def _parse_ts(s):
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        t = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def unsub_url(row):
    token = row.get("unsub_token") or ""
    return APP_URL + "/unsubscribe?t=" + urllib.parse.quote(token)


def digest_key_for(now):
    iso = now.isocalendar()
    return "digest_%d-W%02d" % (iso[0], iso[1])


def due_emails(row, now):
    """Return the list of email_key(s) due for this row right now (usually 0 or 1)."""
    signup = _parse_ts(row.get("signup_at"))
    if not signup or signup < LIFECYCLE_EPOCH:
        return []
    age = now - signup
    activated = bool(row.get("activated_at"))
    due = []

    if age >= dt.timedelta(seconds=0):
        due.append("welcome")
    if not activated and dt.timedelta(hours=24) <= age <= dt.timedelta(hours=72):
        due.append("nudge_24h")
    if activated:
        due.append("activated")
    if not activated and dt.timedelta(days=7) <= age <= dt.timedelta(days=14):
        due.append("nudge_7d")

    prefs = row.get("digest_prefs") or {}
    if activated and prefs.get("enabled") and age >= dt.timedelta(days=7):
        uid = row.get("user_id") or ""
        shard = int(hashlib.sha256(uid.encode()).hexdigest(), 16) % 5
        if shard == now.weekday():
            due.append(digest_key_for(now))

    return due


def weekly_chg_pct(sym):
    """Weekly delta per plan: last close vs close ~5 trading sessions back, from
    state/history/<SYM>.json — never a daily ret_1d. Returns (last, chg_pct) or (None, None)."""
    # sym comes from a user-writable watchlist row. It is interpolated into a filesystem path,
    # and pathlib lets an absolute or ../-bearing value escape STATE entirely — so it is
    # validated against the PSX symbol shape here, at the boundary, not trusted from the DB.
    if not SYMBOL_RE.fullmatch(sym or ""):
        return None, None
    hist = load_json(STATE / "history" / (sym + ".json"), [])
    if len(hist) < 2:
        return None, None
    last_row = hist[-1]
    prior_row = hist[-6] if len(hist) >= 6 else hist[0]
    last = last_row.get("close")
    prior = prior_row.get("close")
    if last is None or not prior:
        return None, None
    return last, (last - prior) / prior * 100


def build_digest_ctx(row):
    """Rule 2: every number comes from state/. Weekly deltas from state/history/<SYM>.json
    (per plan) — never signals/fairvalue/leaderboard/rooms, and never a same-day ret_1d passed
    off as a week's move."""
    watchlist = ((row.get("digest_prefs") or {}).get("watchlist")
                 or (row.get("watchlist")) or [])
    rows = []
    for sym in watchlist[:DIGEST_WATCHLIST_CAP]:
        last, chg = weekly_chg_pct(sym)
        if last is None or chg is None:
            continue
        rows.append((sym, "", last, chg))
    return {"tickers": rows}


def render_email(email_key, row, now):
    base_key = "digest" if email_key.startswith("digest_") else email_key
    fn = BODIES.get(base_key)
    if not fn:
        return None
    ctx = build_digest_ctx(row) if base_key == "digest" else {}
    subject, preheader, rows = fn(ctx)
    html = base(subject, preheader, rows, unsub_url(row))
    return subject, html


def send_via_resend(cfg, to_email, subject, html):
    body = {
        "from": FROM_ADDR,
        "to": [to_email],
        "reply_to": REPLY_TO,
        "subject": subject,
        "html": html,
        "headers": {
            "List-Unsubscribe": "<mailto:hello@henneth.app>, <%s>" % APP_URL,
        },
    }
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "Authorization": "Bearer " + cfg["RESEND_API_KEY"],
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = json.loads(r.read().decode() or "{}")
        return True, raw.get("id"), False
    except urllib.error.HTTPError as e:
        code = e.code
        try:
            detail = json.loads(e.read().decode() or "{}")
        except (ValueError, UnicodeDecodeError):
            detail = {}
        bounce = code in (422, 429) and "bounce" in json.dumps(detail).lower()
        return False, None, bounce
    except urllib.error.URLError:
        return False, None, False


def main(argv):
    send = "--send" in argv
    only = None
    if "--only" in argv:
        i = argv.index("--only")
        only = argv[i + 1] if len(argv) > i + 1 else None
    test_user = None
    if "--test" in argv:
        i = argv.index("--test")
        test_user = argv[i + 1] if len(argv) > i + 1 else None
    requeue_stale = "--requeue-stale" in argv

    cfg, missing = env_config()
    if missing:
        print("lifecycle_email: not configured - missing " + ", ".join(missing) +
              ". Nothing sent. See docs/OPERATIONS.md.")
        return 0

    now = dt.datetime.now(dt.timezone.utc)

    try:
        queue = fetch_queue(cfg, user_id=test_user)
    except (urllib.error.URLError, ValueError) as e:
        print("lifecycle_email: could not read lifecycle_queue (%s) - exiting cleanly." % str(e)[:150])
        return 0

    if not queue:
        print("lifecycle_email: configured, queue empty - nothing to do.")
        return 0

    plan = []
    for row in queue:
        uid = row.get("user_id")
        email = row.get("email")
        if not uid or not email:
            continue
        # Backstop, not the primary gate: lifecycle_queue's own WHERE clause already excludes
        # opted-out users. It is repeated here so that suppression does not live in exactly one
        # place — an edit to that view is a silent way to start mailing people who unsubscribed.
        # Deliberately applies to --test too: opted out means opted out, including for a test.
        if row.get("email_optout"):
            continue
        keys = ["welcome"] if test_user else due_emails(row, now)
        if only:
            keys = [k for k in keys if k == only or (only == "digest" and k.startswith("digest_"))]
        for k in keys:
            plan.append((row, k))

    if not plan:
        print("lifecycle_email: configured, nothing due at %s." % now.isoformat())
        return 0

    # Each plan entry carries the id of an existing log row to RE-CLAIM, or None to insert fresh.
    if test_user:
        plan = [(row, k, None) for row, k in plan]
    else:
        try:
            log_rows = fetch_log_rows(cfg, [row["user_id"] for row, _ in plan])
        except (urllib.error.URLError, ValueError) as e:
            print("lifecycle_email: could not read lifecycle_email_log (%s) - exiting cleanly." % str(e)[:150])
            return 0
        resolved, retries = [], 0
        for row, k in plan:
            prior = log_rows.get((row["user_id"], k))
            if prior is None:
                resolved.append((row, k, None))
            elif retryable(prior, now, force=requeue_stale):
                # Re-claim the row rather than inserting: the unique constraint on
                # (user_id, email_key) means a fresh insert would just 409 and skip, which is
                # why --requeue-stale never actually resent anything before.
                resolved.append((row, k, prior["id"]))
                retries += 1
        plan = resolved
        if retries:
            print("lifecycle_email: %d previously failed/orphaned email(s) queued for one retry." % retries)

    if not plan:
        print("lifecycle_email: configured, nothing left after the already-sent check.")
        return 0

    if not send:
        print("lifecycle_email: DRY RUN - %d email(s) due (%s). Re-run with --send." %
              (len(plan), ", ".join(sorted({k for _, k, _rid in plan}))))
        return 0

    monthly_sent = 0
    if not test_user:
        try:
            monthly_sent = fetch_monthly_sent_count(cfg, now)
        except (urllib.error.URLError, ValueError) as e:
            print("lifecycle_email: could not read monthly sent count (%s) - exiting cleanly." % str(e)[:150])
            return 0
        if monthly_sent >= MONTHLY_CAP:
            print("lifecycle_email: hit MONTHLY_CAP=%d (already %d sent this month) - nothing sent." %
                  (MONTHLY_CAP, monthly_sent))
            return 0

    sent = failed = skipped = 0
    for row, key, retry_id in plan:
        if sent >= DAILY_CAP:
            skipped += len(plan) - sent - failed - skipped
            print("lifecycle_email: hit DAILY_CAP=%d - stopping this run, remainder stays due." % DAILY_CAP)
            break
        if monthly_sent + sent >= MONTHLY_CAP:
            skipped += len(plan) - sent - failed - skipped
            print("lifecycle_email: hit MONTHLY_CAP=%d - stopping this run, remainder stays due." % MONTHLY_CAP)
            break

        log_row_id = None
        if not test_user:
            if retry_id:
                # Re-claiming an existing row: PATCH it back to 'queued' rather than inserting,
                # which the unique constraint would reject. If the PATCH itself fails, skip —
                # sending without a claimed row is how a double-send happens.
                if not claim_log_row(cfg, retry_id):
                    skipped += 1
                    continue
                log_row_id = retry_id
            else:
                log_row_id = reserve_log_row(cfg, row["user_id"], key)
                if log_row_id is None:
                    skipped += 1
                    continue
        # A retry that fails again is marked 'failed_final' — a second terminal status is what
        # bounds retries at exactly one per key without adding an attempts column to the live
        # table. So a permanently broken recipient costs one extra send, once, and never again.
        fail_status = "failed_final" if retry_id else "failed"

        # One bad row must not take the batch down with it: the log row for this recipient is
        # already reserved, so an escaping exception would both abort every remaining send AND
        # strand this key as permanently "queued". Mark it failed and move to the next recipient.
        try:
            rendered = render_email(key, row, now)
            if not rendered:
                if log_row_id:
                    update_log_row(cfg, log_row_id, fail_status)
                failed += 1
                continue
            subject, html = rendered

            ok, resend_id, bounce = send_via_resend(cfg, row["email"], subject, html)
            if ok:
                sent += 1
                if log_row_id:
                    update_log_row(cfg, log_row_id, "sent", resend_id)
            else:
                failed += 1
                if log_row_id:
                    update_log_row(cfg, log_row_id, "bounced" if bounce else fail_status)
                if bounce:
                    set_optout(cfg, row["user_id"])
        except Exception as e:
            failed += 1
            print("lifecycle_email: %s for %s failed (%s) - continuing" % (key, row.get("user_id"), e))
            if log_row_id:
                update_log_row(cfg, log_row_id, fail_status)
        time.sleep(SEND_DELAY_SEC)

    print("lifecycle_email: %d sent, %d failed, %d skipped (already sent/capped) at %s"
          % (sent, failed, skipped, now.isoformat()))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as e:  # noqa: BLE001 — Rule: network/runtime failures never crash the cycle
        print("lifecycle_email: unexpected error (%s) - exiting cleanly, nothing sent." % str(e)[:200])
        sys.exit(0)
