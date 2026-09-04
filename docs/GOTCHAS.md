# Henneth — Gotchas & Conventions

Things that cost real debugging time at least once. Every entry is a trap that looks fine until it
isn't. Read before touching the area named in the heading.

Governance rules live in [`CLAUDE.md`](../CLAUDE.md). Operations (who runs what, where, the publish
path) live in [`OPERATIONS.md`](OPERATIONS.md). This file is the third layer: *the sharp edges*.

---

## Verifying a deploy

**`/state/*` is auth-gated. You cannot verify a state-file push with unauthenticated curl.**
`middleware.js` (matcher `/state/:path*`) verifies Supabase ES256 JWTs and fails closed.
The only exceptions are `PUBLIC_FILES = {natal_ephem.bin, natal_ephem.json, public_probe.json}`.
Everything else returns 401 to a client without a session.

Consequence: a polling loop like `until curl -s .../state/changelog.json | grep -q vX; do sleep 10; done`
can never succeed. It will run forever. Verify instead via the Vercel deployments API — match
`githubCommitSha` against your commit, and require `state: "READY"` and `target: "production"`.

**A signed-out live page emits ~50 console 401s from `/state/*`.** That is the gate working. Not a bug.

**`vercel.json` sets `cleanUrls: true`.** `GET /index.html` returns a 15-byte `Redirecting...` stub,
not the page. Grep against `/`, or use `curl -L`.

## CSS in `dashboard/auth-terminal.css`

**A comment before an at-rule silently kills the rest of the stylesheet.**
`.hn-auth /* note */ .foo{}` is valid — a comment counts as whitespace, so it parses as a descendant
combinator. The same shape in front of `@media` is fatal, and fails quietly: no console error, the
remaining rules just stop existing.

Verify after any comment edit by reading `document.styleSheets[i].cssRules.length` in the browser.
Current count: **303**.

**Centered flex is not linear.** `.left` is `display:flex; align-items:center`. Adding N px of margin
to a child does not move it N px — in one measured case 8px of `.sub` margin moved the sign-in button
11px. Tune empirically and re-measure after every change. Do not compute the delta and trust it.

**Desktop base proportions are frozen** to the owner-endorsed reference. Every anti-scroll trim lives
in `@media (min-width:881px) and (max-height:820px)`, never in base rules. Breakpoints:

| Query | Effect |
|---|---|
| `max-width: 880px` | mobile — hides `.right` (animation panel) and `.nav-right` |
| `max-width: 560px` | also hides `.legal` |
| `min-width:881px and max-height:820px` | desktop short-viewport trim (the no-scroll fix) |

**The file covers three surfaces**, not one: the sign-in / create-account terminal, the post-login
onboarding flow, and the first-view "today" panel. All rules are scoped `.hn-auth …`.

**Its generator is stale.** `scratchpad/gen_auth_css.py` produced the first version out of
`henneth-login-terminal-wake6-v4.html`. The file has been hand-maintained since. Re-running the
generator would silently revert the mobile block, the short-viewport block, and the onboarding styles.
Do not re-run it.

## `dashboard/auth-terminal.js`

Mountable IIFE exposing `window.HennethAuthTerminal` (`mount(tab)`, `unmount`, …). Markup lives in the
`HN_MARKUP` template literal starting around line 14.

`switchTab` is **not** on the live build's exposed object. To drive tabs from a browser probe, click
the `.tab` element instead of calling the API.

`data-gated="1"` on `<body>` strips the desk sidebar and topbar while gated. That is why the logo
lives inside the auth terminal's own `.nav` rather than the shared topbar.

## Browser automation probes

- `javascript_tool` rejects top-level `await`. Wrap probes in `(async()=>{ … })()`.
- Never call `location.reload()` inside a probe — it kills the inspected target mid-execution
  ("Inspected target navigated or closed"). Reload and measure in two separate calls.
- Screenshots at mobile viewport render at devicePixelRatio scaling and can *look* horizontally
  cropped when nothing overflows. Trust `documentElement.scrollWidth` vs `clientWidth`, not the image.

## Concept D marketing homepage

The shared marketing canvas is `--maxw: 1180px`. Below the homepage hero, direct post-hero chapters
use 24 px desktop/tablet and 18 px mobile gutters while their section backgrounds remain full width.
Do not target arbitrary inline values such as `[style*="44px"]` to create those gutters: that also
matches visualization heights, offsets and SVG transform origins. Target direct padded `.hn-rv`
chapters instead.

`Header.astro` owns navigation on every marketing route. Its immersive presentation only applies when
`Base.astro` explicitly receives `navMode="immersive"`; the homepage currently uses the shared default
bar. The mobile drawer breakpoint is 760 px, while compact post-hero rails start at 920 px and reach
their smallest cards at 620 px. Keep the fixed drawer overlay as a sibling outside the transformed or
filtered header so it can cover and blur the full viewport.

The Astro markup's `data-*` hooks and the selectors in `home-concept-d-posthero.ts` are one interface;
changing either side without the other silently disables a chapter. The two WebGL fields use a 120 px
visibility margin and cap DPR at 1.5. Verify both `prefers-reduced-motion` and `scripting: none` paths
before release, and remember that the hero video layer is deliberately absent at 620 px and below.

## Windows / encoding

The console is cp1252. Any script that reads or prints state JSON containing Urdu or em-dashes will
crash with `UnicodeDecodeError` / `UnicodeEncodeError` unless it uses
`io.open(path, encoding='utf-8')` for reads and `json.dumps(..., ensure_ascii=True)` for prints.

## Publishing

`scripts/publish.py --code` ships **only files already staged in git**. It never runs `git add -A`.
Unstaged hand-authored files are left behind on purpose — they may belong to a concurrent session.
That is correct behaviour, not a failure.

Preflight emits a standing benign WARN: newly-added universe tickers still backfilling history
(103 at last count). It never gates publish.

## The ~103 permanently-empty board counters

The KSE All Share constituent list carries PSX board artifacts that are **not companies** — `…NC`
(non-compliant), `…XD` (ex-dividend), `…XB` (ex-bonus), and rights counters. DPS returns zero bars
for them forever. They never gain a `state/history/{SYM}.json`, so they never leave
`fetch_history._pick()`'s never-fetched set, and they are excluded from `coverage.json` (so the
dashboard does not surface them and `data_health.py` does not count them as missing history).

This is inert as long as they stay off the refresh budget. It was **not** inert once: their count
used to be subtracted from `LISTED_PER_RUN`, driving the rotation slice to `max(0, 90 - 103) = 0`.
No listed symbol with an existing series was refreshed on any run for 47 sessions, and
`health.json` stayed green throughout because its freshness test was a `max()` over all symbols.
That is how a July close reached the live site in September.

**Trigger to revisit:** if `state/history_meta.json` `failed` grows past ~150 entries, or if
`attempted` per run climbs near the 25-minute Actions timeout, split the probe out of the per-run
loop entirely (a weekly sweep) rather than widening the budget.

## File mtimes are meaningless in the cloud

`actions/checkout` writes the entire repo fresh at the start of every workflow run, in git index
order — **alphabetical**. Every `state/` file therefore has an mtime that says nothing about when
its contents were produced, and mtime *ordering* degenerates to alphabetical ordering.

This cost a second month of stale prices. After the board-counter starvation above was fixed, the
long-tail rotation still ordered its queue by `st_mtime` ("stalest first"). In the cloud that meant
"alphabetically first", so the same 90 symbols were repriced on every run forever and everything
past roughly the letter H — TATM among them — was never reached at all. Locally the ordering looked
fine, because a local checkout preserves the mtimes of files you didn't touch.

**Rule:** any clock that must survive a run is persisted state, committed with `state/`. The refresh
rotation's clock is `state/history_meta.json` `last_attempt`. `preflight.py` WARNs when a large share
of covered symbols has not been attempted in 3 days, which is the shape both bugs had.

`CHANGELOG.md` uses CalVer: `## YYYY-MM-DD — vYYYY.MM.DD — Title`, with `.2` / `.3` suffixes for extra
same-day releases. `scripts/build_changelog.py` extracts **only** the `<!--public … -->` blocks into
`state/changelog.json` and fails closed — an entry with no public block publishes nothing. That is
intended for internal-only changes.

## Secrets

`config/desk.json` must **never** be served. It holds `capital_pkr` (the owner's actual trading
capital) and the Telegram bot token.

## Known open threads

- `GROQ_API_KEY` is missing on the Vercel deployment — Ask-the-desk returns
  "Chat isn't configured yet — GROQ_API_KEY is missing on the deployment."
- `/cast` (cast a birth chart without an account) is the deliberate signed-out acquisition entry
  point. Do not add it to the members-only route list or remove the public ephemeris exception.
- Proposed, not built: a `desk_profile` jsonb column on the Supabase `profiles` table for
  cross-device onboarding persistence.
