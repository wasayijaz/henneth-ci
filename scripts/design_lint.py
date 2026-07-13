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
