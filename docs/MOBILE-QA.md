# Mobile QA — the recurring checklist

Run this before calling any mobile-facing change finished. It applies to the dashboard
(`dashboard/`) and, where noted, the marketing site (`site/`).

Henneth is **not a native app**. It is a static, hash-routed single-page dashboard plus an Astro
marketing site, both served from Vercel. So the native-app QA vocabulary needs translating before
it is useful here:

| Native concept | What it means for Henneth |
|---|---|
| System Back button | The phone's Back gesture / button acting on browser history |
| Deep link | A shared `#/...` URL |
| App lifecycle (background/foreground) | Tab visibility, and whether `state/*.json` is stale on return |
| Push notifications | **N/A.** `dashboard/push.js` and `dashboard/sw.js` are dead code; push was started and abandoned |
| OS permission prompts | **N/A.** The desk requests no camera, mic, photos, contacts, or location |
| Process death / low-memory reconstruction | **N/A.** A tab reload rebuilds everything from `state/*.json` |
| Split screen, incoming call, alarm, biometric prompt | **N/A** |
| SMS OTP autofill | **N/A.** Auth is Supabase email confirmation |

## The one rule that catches most missed fixes

**Mobile CSS in this repo is theme-scoped.** Phone styles live inside `body[data-theme=gemini]`
blocks in `dashboard/themes.css`. A rule written outside that scope never reaches the phone, even
though it looks correct in the file and correct in a desktop browser at a narrow width.

Before you call a mobile CSS fix done, confirm the selector you edited is inside a
`body[data-theme=gemini]` block.

## Part 1 — Automated (advisory)

These run in `scripts/design_lint.py`, which `preflight.py` invokes on every publish.
`design_lint.py` is **advisory and never fails a build** — it reports, it does not gate. Read its
output; do not assume a clean publish means a clean mobile pass.

```bash
python scripts/design_lint.py
```

What it checks:

1. Every mobile-reachable `<input>` declares an `inputmode`, or a `type` that implies one
   (`search`, `email`, `tel`).
2. Inputs inside a form declare `enterkeyhint`, so the phone's Return key says something useful.
3. `type="number"` is flagged — on mobile it shows a spinner and silently changes value when the
   user scrolls over it. `inputmode="decimal"` (or `"numeric"` for whole numbers) is the fit.
4. Any class toggled via the `hidden` DOM property has a paired
   `.class[hidden]{display:none!important}` rule. This is a documented repeat bug in this repo —
   see `docs/OPERATIONS.md` §9. Without the pairing you get flashing or stuck states.
5. Direction is not carried by colour alone. `--up` / `--dn` need a sibling glyph or sign.
6. Interactive elements inside the mobile theme scope declare a touch target of at least 44px.

## Part 2 — The human pass, on a real phone

Automation cannot see any of this. Do it on an actual handset, not a desktop browser resized
narrow — the resized desktop has a mouse, a hardware keyboard, an Escape key, and no notch.

1. **Back button.** Open every overlay — Desk Room replay, the `+` launcher scrim, search, the
   mobile drawer, the account menu — and press system Back. It must close the overlay. It must not
   leave the desk.
2. **Keyboard.** Tap each input. Is the keypad right (letters vs digits vs decimal)? Does the
   Return key say something sensible? Does the keyboard cover the submit button?
3. **Double-tap.** Tap every submit and every action button twice, fast. Nothing may fire twice.
   The "ask the desk" path costs real money per call — a double submit is a double bill.
4. **Airplane mode mid-action.** Start an action, kill the connection. The user must get an
   explanation, not silence.
5. **One-handed thumb test.** Can every primary action be reached with one thumb?
6. **Urdu plus largest system text.** Switch language to Urdu and set iOS/Android text size to its
   largest. Urdu is a second string set rendered inside an LTR layout — it is the wrapping
   stressor. Nothing may clip or overlap.
7. **Empty state.** Sign in as a brand-new account with no watchlist and no history. Every page
   must say something, not render blank.
8. **Landscape on a notched phone.** Rotate. Content must not sit under the notch or the home
   indicator.
9. **Leave it an hour, then tap.** `middleware.js` fails closed; an expired session makes
   `/state/*` return 401. The user must be told and given a way back in, not shown a dead screen.
10. **Confirm the scope.** Re-read the CSS you changed and confirm it is inside
    `body[data-theme=gemini]`.

## Verification commands

```bash
node -c dashboard/app.js
python scripts/design_lint.py
python scripts/preflight.py
```

## The marketing site (`site/`)

The Astro site is a separate surface with its own mobile rules — it has no `data-theme` scoping and
no auth gate, so every check below is provable signed-out with a dev server and a 375px viewport.

- **Touch targets are enforced with `@media (pointer: coarse)`, not a width breakpoint.** The
  desktop metrics stay exactly as designed; only touch devices get the bigger hit area. Two rules
  exist today: `.ft-social-link` (32px box → 44px) in `Footer.astro`, and `.seg-2` (9.5px mono
  text, ~16px tall → `min-height: 44px`) in `index.astro` and `solutions.astro`.
- **`.seg-2` is duplicated in two pages.** Changing one without the other silently regresses the
  home page or `/solutions`. Grep before you edit.
- **Every calculator input already carries `inputmode="decimal"`** — they all come from the single
  `ToolPage.astro` field loop, so the hint is set once and covers all seven tools. Do not add a
  bare `<input type="number">` anywhere else.
- **Astro's component-scoped CSS does not always hot-reload.** A style edit inside a `.astro`
  component can leave the dev server serving the old rule while page-level styles update fine.
  If a rule looks like it did not apply, restart the dev server before you go debugging the CSS.

Verify with `cd site && npm run build`, then grep the built CSS for the rule you added — the
production bundle is the thing that ships, not the dev server's view of it.
