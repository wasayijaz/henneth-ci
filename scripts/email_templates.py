"""
Email template system for Henneth's lifecycle emails — stdlib string templating, no new deps.

base() is the ONLY entry point callers should use. It ALWAYS calls footer() itself, so no caller
can ship an email missing the "Research - not advice" disclaimer or the unsubscribe link — the
assert below makes that structurally impossible, not just a convention.

block_ticker_row(sym, name, last, chg_pct) is the ONLY way a ticker can reach an email body — a
four-field allowlist. This is the SECP Reg 2(ha) compliance surface: no verdict, price target,
stop, entry, or R:R can pass through this signature. Do not widen it; if a caller needs more than
these four fields, that is exactly the shape of content this module exists to keep out.

Brand tokens mirror site/src/styles/global.css:26-63 (do not drift from that file without
updating this comment). Square corners are the brand's defining trait
(site/src/styles/global.css:67, "nothing is ever rounded") — email clients ignore
`border-radius: 0`'s intent by default (rectangles already have no radius), so the rule below is
belt-and-braces against any client that applies its own rounding to buttons/tables.

Every caller-supplied string is HTML-escaped at the point of interpolation. These templates are
built with str.format, which does no escaping of its own, and the ticker/CTA/note values reach
here from user-writable rows (watchlists, profile fields) — unescaped they are an HTML-injection
hole into somebody else's inbox. Escape at interpolation, never at the call site.
"""
from html import escape as _esc

BG = "#f5f3ef"
INK_1 = "#0a0a0a"
INK_2 = "#5a5a63"
LINE = "#ddd9d1"
UP = "#186b4c"
DN = "#ad3b26"
FONT = "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"

DISCLAIMER = "Research · not advice."


def footer(unsub_url):
    """The only place the disclaimer and unsubscribe link are written. base() always calls this."""
    assert unsub_url and unsub_url.startswith("http"), "footer() needs a real unsubscribe URL"
    return """
    <tr><td style="padding:24px 32px;border-top:1.5px solid {line};">
      <p style="margin:0 0 8px;font-family:{font};font-size:11px;color:{ink2};line-height:1.6;">
        {disclaimer}<br>
        Henneth is a personal research desk. Nothing here is investment advice, and nothing here
        is a solicitation to buy or sell any security.
      </p>
      <p style="margin:0;font-family:{font};font-size:11px;color:{ink2};">
        <a href="{unsub}" style="color:{ink2};">Manage email preferences / unsubscribe</a>
      </p>
    </td></tr>""".format(line=LINE, font=FONT, ink2=INK_2, disclaimer=DISCLAIMER,
                          unsub=_esc(unsub_url))


def base(subject, preheader, body_rows, unsub_url):
    """
    subject: also used as the <title>.
    preheader: hidden preview text most inbox clients show next to the subject line.
    body_rows: pre-built HTML string of <tr> blocks from the block_* helpers below — NOT raw
        caller-supplied content, so the blocks stay the only path into the email body.
    unsub_url: required, no default, forwarded straight to footer().
    """
    foot = footer(unsub_url)
    assert DISCLAIMER in foot, "disclaimer missing from footer - refusing to build email"
    # compare against the escaped form — footer() escapes before interpolating, so a raw-string
    # check here would fail on any unsubscribe URL carrying a query string.
    assert _esc(unsub_url) in foot, "unsubscribe url missing from footer - refusing to build email"

    return """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{subject}</title>
</head>
<body style="margin:0;padding:0;background:{bg};">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{preheader}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{bg};">
    <tr><td align="center" style="padding:32px 16px;">
      <!-- outer td = dark fill, offset by padding-right/bottom = hard-shadow illusion
           (no box-shadow support in Outlook's Word rendering engine) -->
      <table role="presentation" width="600" cellpadding="0" cellspacing="0"
             style="width:600px;max-width:100%;background:{ink1};padding:0 8px 8px 0;">
        <tr><td>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                 style="background:#ffffff;border:1.5px solid {ink1};border-radius:0;">
            <tr><td style="padding:24px 32px;border-bottom:1.5px solid {ink1};">
              <span style="font-family:{font};font-size:18px;font-weight:700;color:{ink1};
                           letter-spacing:0.5px;">HENNETH</span>
            </td></tr>
            {rows}
            {footer}
          </table>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>""".format(subject=_esc(subject), preheader=_esc(preheader), bg=BG, ink1=INK_1,
                   font=FONT, rows=body_rows, footer=foot)


def block_ticker_row(sym, name, last, chg_pct):
    """The only ticker renderer — exactly symbol/name/last/%change, nothing else. See module
    docstring: this signature IS the compliance guardrail, not a convenience wrapper."""
    color = UP if chg_pct >= 0 else DN
    sign = "+" if chg_pct >= 0 else ""
    return """
    <tr><td style="padding:16px 32px;border-bottom:1px dotted {line};">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
        <td style="font-family:{font};font-size:14px;color:{ink1};font-weight:700;">{sym}</td>
        <td style="font-family:{font};font-size:12px;color:{ink2};">{name}</td>
        <td align="right" style="font-family:{font};font-size:14px;color:{ink1};">{last}</td>
        <td align="right" style="font-family:{font};font-size:13px;color:{color};width:70px;">
          {sign}{chg:.1f}%
        </td>
      </tr></table>
    </td></tr>""".format(line=LINE, font=FONT, ink1=INK_1, ink2=INK_2, color=color,
                          sym=_esc(str(sym)), name=_esc(str(name)), last=_esc(str(last)),
                          sign=sign, chg=chg_pct)


def block_cta(label, url):
    return """
    <tr><td style="padding:24px 32px;" align="center">
      <a href="{url}" style="display:inline-block;padding:12px 28px;background:{ink1};color:#fff;
         font-family:{font};font-size:13px;font-weight:700;text-decoration:none;border-radius:0;
         letter-spacing:0.5px;">{label}</a>
    </td></tr>""".format(url=_esc(url), ink1=INK_1, font=FONT, label=_esc(label))


def block_note(text):
    return """
    <tr><td style="padding:8px 32px 24px;">
      <p style="margin:0;font-family:{font};font-size:13px;color:{ink2};line-height:1.6;">
        {text}
      </p>
    </td></tr>""".format(font=FONT, ink2=INK_2, text=_esc(text))
