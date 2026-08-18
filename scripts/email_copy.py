"""
The five lifecycle email bodies (welcome, nudge_24h, activated, digest, nudge_7d) — kept apart
from scripts/email_templates.py so copy edits never touch layout code.

Every function returns (subject, preheader, body_rows) where body_rows is a ready string of <tr>
blocks for email_templates.base(). Callers (scripts/lifecycle_email.py) supply ctx — a dict — and
own reading state/*.json; this module never touches the filesystem, so it stays fact-blind and
testable with plain dicts.
"""

from email_templates import block_cta, block_note, block_ticker_row

APP_URL = "https://desk.henneth.app"


def welcome(ctx):
    subject = "Welcome to Henneth"
    preheader = "Pick a ticker and the desk starts working for you."
    rows = (
        block_note(
            "Henneth is a research desk for the Pakistan Stock Exchange. No wizard, no quiz — "
            "pick one ticker on the Today page and the desk starts tracking it for you."
        )
        + block_cta("Pick a ticker", APP_URL + "/today")
        + block_note(
            "Add a stock to your watchlist, look up a Desk Room debate, or run the position-size "
            "calculator — any of these gets you started."
        )
    )
    return subject, preheader, rows


def nudge_24h(ctx):
    subject = "Still there? Pick a ticker to get started"
    preheader = "One click starts the desk tracking a stock for you."
    rows = (
        block_note(
            "You signed up yesterday but haven't picked a ticker yet. The desk needs one stock "
            "to start showing you anything useful — takes ten seconds."
        )
        + block_cta("Pick a ticker", APP_URL + "/today")
    )
    return subject, preheader, rows


def activated(ctx):
    subject = "You're set up — here's what the desk tracks"
    preheader = "Watchlist, Desk Room debates, and the weekly digest, explained."
    rows = (
        block_note(
            "Nice — you're now tracking a stock on the desk. From here: the Today page follows "
            "your watchlist, the Desk Room has a bull/bear debate on any ticker, and you can turn "
            "on the weekly digest any time from settings."
        )
        + block_cta("Open the desk", APP_URL + "/today")
    )
    return subject, preheader, rows


def digest(ctx):
    """ctx must include 'tickers': [(sym, name, last, chg_pct), ...] — already read from
    state/quant.json / state/live.json by the caller. This function only lays copy out."""
    subject = "Your weekly desk digest"
    preheader = "This week's watchlist moves, in one email."
    rows = block_note("Here's how your watchlist moved this week:")
    for sym, name, last, chg_pct in ctx.get("tickers", []):
        rows += block_ticker_row(sym, name, last, chg_pct)
    rows += block_note(
        "Full detail, Desk Room debates, and the calendar are on the desk."
    ) + block_cta("Open the desk", APP_URL + "/today")
    return subject, preheader, rows


def nudge_7d(ctx):
    subject = "One week in — still haven't picked a ticker"
    preheader = "The desk works once you give it one stock to follow."
    rows = (
        block_note(
            "It's been a week and the desk hasn't got a stock to follow yet. Pick any PSX ticker "
            "and everything else — watchlist tracking, Desk Room debates, the weekly digest — "
            "follows from there."
        )
        + block_cta("Pick a ticker", APP_URL + "/today")
    )
    return subject, preheader, rows


BODIES = {
    "welcome": welcome,
    "nudge_24h": nudge_24h,
    "activated": activated,
    "digest": digest,
    "nudge_7d": nudge_7d,
}
