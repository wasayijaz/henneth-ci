#!/usr/bin/env python3
"""Design-system lint (deterministic, zero tokens).

The free first layer of the UI QA system. Scans the dashboard's CSS/HTML for
violations of the desk's locked design language so drift is caught mechanically
before the design-reviewer agent (expensive) is ever needed. Catches the class of
issue the owner flagged: rounded corners sneaking in, inconsistent box padding,
raw hex colors bypassing the token system.

Design language (locked):
  - every corner HARD: border-radius is always 0
  - colors come from CSS variables (--ink/--line/--up/--dn/...), not raw hex, except
    inside the single token-definition block
  - boxed components use 1.5px solid var(--line)

Writes state/design_lint.json and prints a summary. Non-fatal (advisory) — it informs,
it doesn't block a deploy, so a cosmetic nit never stops the desk shipping.
"""
import re
import time

from psx_data import STATE, ROOT, save_json

CSS = ROOT / "dashboard" / "themes.css"
JS = ROOT / "dashboard" / "app.js"
DASHBOARD = ROOT / "dashboard"


def lint():
    findings = []
    css = CSS.read_text(encoding="utf-8") if CSS.exists() else ""
    js = JS.read_text(encoding="utf-8") if JS.exists() else ""

    # 1) non-zero border-radius anywhere (the hard-corner rule)
    for i, line in enumerate(css.splitlines(), 1):
        for m in re.finditer(r"border-radius:\s*([^;}\s]+)", line):
            v = m.group(1)
            if v not in ("0", "0px", "0!important") and "var(" not in v:
                findings.append({"sev": "high", "file": "themes.css", "line": i,
                                 "msg": f"non-zero border-radius '{v}' — the UI is hard-cornered (radius 0)"})
    for m in re.finditer(r"border-radius:\s*([0-9]+(?:\.[0-9]+)?(?:px|em|rem|%))", js):
        findings.append({"sev": "high", "file": "app.js",
                         "msg": f"inline non-zero border-radius '{m.group(1)}' — use 0"})

    # 2) raw hex colors outside the token block (should use var(--...))
    token_block = re.search(r"body\[data-theme=gemini\]\{.*?\}", css, re.S)
    tb = token_block.group(0) if token_block else ""
    for i, line in enumerate(css.splitlines(), 1):
        if line in tb:
            continue
        for m in re.finditer(r"#[0-9a-fA-F]{3,6}\b", line):
            # allow pure white/black shorthands used for on-color text
            if m.group(0).lower() in ("#fff", "#ffffff", "#000", "#000000", "#f4f4f0", "#333"):
                continue
            findings.append({"sev": "low", "file": "themes.css", "line": i,
                             "msg": f"raw hex {m.group(0)} outside the token block — prefer var(--...)"})

    # 3) card padding sanity: the gemini .card zeroes its own padding and pads children;
    #    flag if that contract is broken (a common source of "box has no padding")
    if "body[data-theme=gemini] .card>*:not(h2):not(.sub)" not in css:
        findings.append({"sev": "medium", "file": "themes.css",
                         "msg": "the .card child-padding contract is missing — inner content may touch the border"})

    # 4) TYPOGRAPHY hierarchy: readable sizes + a controlled scale (info must present well)
    sizes = [float(m.group(1)) for m in re.finditer(r"font-size:\s*([0-9]+(?:\.[0-9]+)?)px", css)]
    tiny = sorted({s for s in sizes if s < 9})
    if tiny:
        findings.append({"sev": "medium", "file": "themes.css",
                         "msg": f"font-size(s) below 9px {tiny} — too small to read comfortably on mobile"})
    distinct = sorted(set(sizes))
    if len(distinct) > 16:
        findings.append({"sev": "low", "file": "themes.css",
                         "msg": f"{len(distinct)} distinct font-sizes — a tight type scale reads as one "
                                f"system; consider consolidating near values"})
    # near-duplicate sizes (e.g. 12 and 12.5 and 13 all present) blur the hierarchy
    near = [(a, b) for a, b in zip(distinct, distinct[1:]) if 0 < b - a < 0.75]
    if len(near) > 4:
        findings.append({"sev": "low", "file": "themes.css",
                         "msg": f"{len(near)} pairs of near-identical font sizes (e.g. {near[0]}) — "
                                f"collapse them so size differences signal real hierarchy"})
    # body base should be a comfortable reading size
    m = re.search(r"body\[data-theme=gemini\]\{[^}]*font-size:\s*([0-9.]+)px", css)
    if m and float(m.group(1)) < 12:
        findings.append({"sev": "low", "file": "themes.css",
                         "msg": f"base body font-size {m.group(1)}px is small for dense financial text"})

    # 5) MOBILE checks. Reminder for future agents: the mobile theme scope in this repo is
    #    `body[data-theme=gemini]{...}` blocks in themes.css — a mobile-intent CSS fix placed
    #    outside that scope never reaches the phone.
    js_files = sorted(DASHBOARD.glob("*.js"))
    html_files = sorted(DASHBOARD.glob("*.html"))
    css_files = sorted(DASHBOARD.glob("*.css"))

    input_tag_re = re.compile(r"<input\b[^>]*>", re.I)

    for path in js_files + html_files:
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            for m in input_tag_re.finditer(line):
                tag = m.group(0)
                type_m = re.search(r'type=["\']([\w-]+)["\']', tag, re.I)
                itype = (type_m.group(1).lower() if type_m else "text")
                has_inputmode = re.search(r"inputmode=", tag, re.I) is not None
                has_enterkeyhint = re.search(r"enterkeyhint=", tag, re.I) is not None

                # 5a) MISSING_INPUTMODE — text/number inputs w/o inputmode and not
                #     already using a semantic type (search/email/tel) that implies a keypad.
                if itype in ("text", "number") and not has_inputmode and itype not in ("search", "email", "tel"):
                    want = "numeric\" or \"decimal" if itype == "number" else "the matching semantic keypad (e.g. numeric/decimal/search)"
                    findings.append({"sev": "low", "file": path.name, "line": i,
                                     "msg": f"<input type=\"{itype}\"> has no inputmode= — mobile shows the "
                                            f"full alphabetic keyboard; probably wants inputmode=\"{want}\""})

                # 5b) MISSING_ENTERKEYHINT — advisory only, not every input needs one.
                if not has_enterkeyhint:
                    findings.append({"sev": "info", "file": path.name, "line": i,
                                     "msg": "<input> has no enterkeyhint= — consider one (e.g. \"search\"/"
                                            "\"done\"/\"next\") so the mobile return key labels itself"})

                # 5c) NUMBER_INPUT_ON_MONEY
                if itype == "number":
                    findings.append({"sev": "low", "file": path.name, "line": i,
                                     "msg": "type=\"number\" shows a spinner on mobile and changes value on "
                                            "scroll-over; prefer inputmode=\"decimal\" (or \"numeric\" for "
                                            "integers) on a text input instead"})

    # 5d) HIDDEN_WITHOUT_CSS_GUARD — the repeat bug documented in docs/OPERATIONS.md #9:
    #     JS toggles `.hidden` on a class-addressed element but no CSS rule enforces
    #     `display:none!important` under `[hidden]`, so a stylesheet rule with higher
    #     specificity can leave the "hidden" element visible. Only resolves the case where
    #     the element is addressed directly by a class selector in the same expression —
    #     id-addressed toggles (the vast majority in this repo) are skipped silently rather
    #     than risk a false positive.
    all_css = "\n".join(p.read_text(encoding="utf-8") for p in css_files)
    hidden_toggle_re = re.compile(
        r"""(?:querySelector|\$)\(\s*['"]\.([\w-]+)['"]\s*\)\s*\.\s*hidden\s*=\s*(?:true|false)"""
        r"""|(?:querySelector|\$)\(\s*['"]\.([\w-]+)['"]\s*\)\s*\.\s*toggleAttribute\(\s*['"]hidden['"]""",
        re.I,
    )
    for path in js_files:
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            for m in hidden_toggle_re.finditer(line):
                cls = m.group(1) or m.group(2)
                guard_re = re.compile(
                    r"\." + re.escape(cls) + r"\[hidden\]\s*\{[^}]*display\s*:\s*none\s*!important",
                    re.I,
                )
                if not guard_re.search(all_css):
                    findings.append({"sev": "medium", "file": path.name, "line": i,
                                     "msg": f"JS toggles .{cls}'s `hidden` property but no CSS rule "
                                            f".{cls}[hidden]{{display:none!important}} exists in dashboard/*.css "
                                            f"— see docs/OPERATIONS.md #9"})

    # 5e) COLOR_ONLY_STATUS — informational only, and noisy by design: every use of the
    #     up/down tokens as a bare color/background is listed so the author can double check
    #     a glyph or sign also conveys the direction, not hue alone. No action is implied.
    color_only_re = re.compile(
        r"\b(color|background(?:-color)?)\s*:\s*(var\(--up\)|var\(--dn\)|#186b4c|#ad3b26)(?![\w-])", re.I
    )
    for path in css_files:
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            for m in color_only_re.finditer(line):
                findings.append({"sev": "info", "file": path.name, "line": i,
                                 "msg": f"{m.group(1)}:{m.group(2)} — up/down conveyed by color only here; "
                                        f"confirm a glyph or sign (▲/▼, +/-) also carries the meaning"})

    # 5f) TOUCH_TARGET — inside body[data-theme=gemini] (the mobile theme scope), an
    #     interactive rule that sets height/padding without a >=44px min-height risks a
    #     touch target under Apple/Google's 44px guidance. Conservative: single-line rules
    #     only, and skipped entirely (not flagged) whenever a min-height is already present,
    #     since reliably parsing its computed value against other declarations is out of
    #     scope for a regex lint.
    touch_rule_re = re.compile(
        r"body\[data-theme=gemini\]\s*([^{}]*\b(?:button|\.btn|\[onclick\])[^{}]*)\{([^}]*)\}",
        re.I,
    )
    for i, line in enumerate(css.splitlines(), 1):
        for m in touch_rule_re.finditer(line):
            selector, body = m.group(1).strip(), m.group(2)
            if "min-height" in body.lower():
                continue
            if re.search(r"\bheight\s*:", body, re.I) or re.search(r"\bpadding\b", body, re.I):
                findings.append({"sev": "low", "file": "themes.css", "line": i,
                                 "msg": f"'{selector}' sets height/padding with no min-height — mobile touch "
                                        f"targets want >=44px; add min-height:44px"})

    highs = sum(1 for f in findings if f["sev"] == "high")
    out = {
        "findings": findings,
        "_meta": {"built": time.strftime("%Y-%m-%d %H:%M"), "total": len(findings),
                  "high": highs, "escalate": highs > 0,
                  "note": "Deterministic design-language lint. 'high' = a rule violation on screen. "
                          "If escalate, run the design-reviewer agent (visual web+mobile pass)."},
    }
    save_json(STATE / "design_lint.json", out)
    print(f"design lint: {len(findings)} findings ({highs} high) -> state/design_lint.json")
    for f in findings[:8]:
        print(f"  [{f['sev']}] {f['file']}: {f['msg']}")
    return out


if __name__ == "__main__":
    lint()
