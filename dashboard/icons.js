/* ============================================================
   Production script — desk-wide tile icons (the REGISTRY half).
   Additive only. Classic script, no module, no build step.
   Linked from dashboard/index.html AHEAD of app.js, which calls
   iconify(document) from its flush() pass (between restackTables()
   and translateTree()).

   What it does: nothing but write one attribute. For every heading
   it recognises it sets data-icon="<slug>"; for every heading it
   does not recognise it sets data-icon="" so the element is never
   re-scanned. It inserts no nodes, reads no network, registers no
   observer of its own, and exports nothing. The glyph itself is
   painted entirely by dashboard/icons.css via ::before, which is why
   Urdu i18n cannot touch it — translateTree() walks TEXT nodes and a
   fixed attribute whitelist (placeholder/title/aria-label), and a
   pseudo-element is in neither.

   THE ONE RULE A FUTURE EDITOR MUST NOT BREAK
   A slug lives in TWO files. Adding, renaming or removing one here
   means doing the same in dashboard/icons.css. A slug present here
   with no matching `[data-icon="<slug>"] { --gi: ... }` rule paints a
   solid 11px block — that is the deliberate loud failure, not a bug
   to patch in CSS with a catch-all.

   Keys are NORMALISED heading text: lowercased, every run of
   non-alphanumerics collapsed to one space, trimmed. So "KEY RISKS",
   "Key risks" and "Key  risks!" are all the key "key risks".
   Headings whose text is interpolated at render time (a ticker, a
   count, a year) can never be keyed by exact text and are left bare
   on purpose — see the notes at the foot of the registry.
   ============================================================ */
"use strict";

/* Normalised heading text -> slug. Frozen: the registry is data, not state. */
var ICON_SLUGS = Object.freeze({
  /* --- Board tiles (.tile-head .tile-title) --- */
  "strategy research": "research",
  "universe heatmap": "heatmap",
  "market data": "marketdata",
  "indices": "indices",

  /* --- Home / desk cards --- */
  "live triggers": "triggers",
  "positions": "positions",
  "proven strategies": "strategy",
  "strategies": "strategy",
  "universe": "universe",
  "predictability": "predictability",
  "news wire": "news",
  "agent wire": "agents",
  "psx indices": "indices",
  "the desk room": "desk",
  "the signal stack": "signalstack",
  "daily read": "dailyread",

  /* --- Macro, geopolitics, risk --- */
  "pakistan macro": "macro",
  "geopolitical risk radar": "geo",
  "key risks": "risk",
  "risk profile": "riskprofile",
  "sectors to watch": "sectors",
  "sectors": "sectors",
  "what actually moves each sector": "drivers",
  "what moves psx": "psx",
  "names on the desk s radar": "radar",

  /* --- Screening and valuation --- */
  "today s scanner": "scanner",
  "screener": "screener",
  "value screen price vs model fair value": "valuation",
  "fair value model": "fairvalue",
  "compare": "compare",
  "evidence alignment": "evidence",

  /* --- Single-stock page --- */
  "key facts": "facts",
  "quant snapshot": "quant",
  "business scorecard": "scorecard",
  "what the data flags": "dataflags",
  "dividends": "dividends",
  "news developments": "developments",
  "insider off market activity": "insider",
  "can you actually trade it": "tradable",
  "what the brokers say": "brokers",

  /* --- Dividends and calendar --- */
  "upcoming dividends book closures": "bookclose",
  "past payouts": "payouts",
  "earnings calendar": "calendar",

  /* --- Research library and track records --- */
  "the library": "library",
  "research library": "library",
  "broker notes": "brokers",
  "company filings briefings": "filings",
  "track records": "trackrecord",
  "the desk s ai analysts": "analysts",
  "brokers ranked on what came true": "brokerrank",
  "broker calls on the record pending": "brokerpending",

  /* --- Learn --- */
  "learn": "learn",
  "deep dives": "deepdives",
  "the beginner s checklist": "checklist",
  "glossary": "glossary",
  "practice portfolio": "practice",

  /* --- Portfolio, watchlist, holdings --- */
  "your portfolio": "portfolio",
  "portfolio x ray": "xray",
  "concentration": "concentration",
  "sector concentration": "sectorconc",
  "your watchlist": "watchlist",
  "on your watchlist": "watchlist",
  "what changed": "changed",
  "holdings": "holdings",
  "dividends received": "divreceived",
  "trade log": "tradelog",

  /* --- Tools --- */
  "tools": "tools",
  "position sizer": "sizer",
  "scenarios": "scenarios",
  "ask the desk": "ask",

  /* --- Community and marketplace --- */
  "members": "members",
  "strategy marketplace": "marketplace",
  "request a strategy": "request",
  "your board": "yourboard",
  "recently shipped": "shipped",

  /* --- Account and settings --- */
  "settings": "settings",
  "your plan": "plan",
  "plans": "plan",
  "your birth details": "birth",
  "your digest": "digest",
  "email preferences": "emailprefs",
  "followed broker desks": "followed",
  "legal": "legal",
  "your private note": "note"

  /* Deliberately absent, and why:
     - "All {n} strategies tested here", "{N}-year behavior",
       "Strategies proven on {ticker}" — text is interpolated at render
       time, so no exact key can match. Left bare rather than faked.
     - "What's new" — modal dialog chrome, not a desk surface.
     - "Priced below/above model fair value" — sub-splits sitting under
       an already-iconed "Value screen" heading.
     - "At a glance", "Become an investor",
       "Learn with PKR 500,000 you can't lose" — restatements inside a
       section that already carries its parent's glyph.
     - "Same question, different horizons", "Every payout in the window",
       "Against the desk's own rules" — tool sub-results, not sections.
     Icon the heading that names a surface; leave the ones nested inside
     it bare, or the emphasis flattens and the icons become noise. */
});

/* The two heading patterns on the desk. The :not([data-icon]) guard is
   what makes iconify() idempotent and O(new nodes) on every flush().

   `#view .seg > h2` is the section divider — <div class="seg"><h2>..</h2>
   <div class="ln"></div><span class="pill">..</span></div> — and it is the
   single most common heading on the desk, so leaving it out would strand
   most of the registry above. It was verified to the same bar as the tile
   title before being added: .seg is display:flex and its h2 a plain block
   flex item (themes.css:1589-1591); no sheet sets `content` or a ::before
   on it (its only rules are white-space:nowrap, plus normal at the wrap
   breakpoint, themes.css:1782); tileify() cannot reach it, its child gate
   admits only DIV and TABLE; and translateTree() sees neither attributes
   outside placeholder/title/aria-label nor pseudo-elements. Scoped to
   #view (the <main>, index.html:352) so modal chrome such as the
   `.wn-top h2` in the What's-new dialog is never swept in.

   `#view .card > h2` is deliberately NOT here. Marking every card head put a
   glyph beside roughly 77 headings, which flattened the page instead of
   ranking it — when every head has a mark, no head is marked. Icons now sit
   only on the two ranks that actually divide a page: the section divider and
   the Board tile. Keep it that way; the registry above intentionally holds
   more slugs than are reachable from these two selectors. */
var ICON_HEADINGS = [
  "#view .seg > h2:not([data-icon])",
  ".tile-head .tile-title:not([data-icon])"
];

function iconNormalize(s) {
  return String(s == null ? "" : s).toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function iconify(root) {
  var scope = root || document;
  if (!scope || typeof scope.querySelectorAll !== "function") return;
  for (var i = 0; i < ICON_HEADINGS.length; i++) {
    var list = scope.querySelectorAll(ICON_HEADINGS[i]);
    for (var j = 0; j < list.length; j++) {
      var el = list[j];
      /* typeof guard: a heading reading "constructor" or "toString" would
         otherwise pull a function off Object.prototype. */
      var slug = ICON_SLUGS[iconNormalize(el.textContent)];
      el.setAttribute("data-icon", typeof slug === "string" ? slug : "");
    }
  }
}
