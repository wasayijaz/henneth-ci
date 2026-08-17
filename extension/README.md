# Henneth Desk Companion — Chrome Extension

Read-only PSX research companion. Detects the ticker you're looking at on
TradingView or the PSX DPS site and shows the desk's read for it — the same
public-safe state the dashboard renders. It never places orders and never
uses advice language.

## Load it (Developer Mode)

1. Open Chrome → chrome://extensions
2. Enable "Developer mode" (top right)
3. "Load unpacked" → select this folder (extension/)
4. Log in at https://desk.henneth.app once — the extension picks up the
   session token automatically from that tab
5. Open a PSX chart on TradingView (e.g. ?symbol=PSX:LUCK) and click the
   extension icon — the side panel loads the desk's read for that ticker

## What it shows

- Health banner — data layer status, gate for everything else
- Context card — price, 1d/5d/20d moves, RSI, trend vs MA20/50, ADTV, predictability
- Valuation — the desk's composite fair-value model verdict
- Active setup — if a proven strategy is triggering (always labelled
  "backtest-proven, unaudited"; degrades visibly when health != ok)
- Liquidity reality check — ADTV, spread estimate, days-to-exit (stressed),
  grade, signal eligibility, zero-volume flags
- Dividends & dates — book closure, buy-by, estimated yield, results dates
- Strategy evidence — patterns historically proven on the name (evidence only)
- Position size calculator — your capital/entry/stop + desk Rule 4 constants

## Tabs

- **Read** — hero price header, one-glance verdict strip (trend / valuation /
  liquidity grade / predictability), meters for RSI, predictability and
  mispricing, plus all the cards below.
- **Notes** — per-ticker private notes synced to your account via the same
  profiles.notes the desk ticker pages use. Create, edit, delete; a note
  written here appears on the desk and vice versa (last-write-wins, same as
  two browser tabs).

## Ticker detection sites

- TradingView (chart ?symbol=PSX:SYM and symbol pages)
- PSX DPS portal
- PSX business press: Dawn, Profit.pk, Business Recorder, Tribune, Mettis,
  The News — text scan of title/headings/body against the desk universe,
  picking the most-mentioned known ticker (headline mentions count extra)

## Architecture

- extension/manifest.json — MV3, side panel, content scripts
- auth.js — content script on desk.henneth.app; reads the dashboard's own
  Supabase localStorage key and stores the token in chrome.storage.local.
  The token never leaves local storage; all fetches mirror the dashboard's
  Authorization header against the same /state/*.json contract.
- detector.js — content script on TradingView / DPS; URL+title ticker
  detection, re-checks on SPA navigation every 1.5s
- background.js — opens the side panel on icon click; remembers last ticker
- api.js — authenticated fetch layer with 60s TTL cache; PKT-safe date labels
- panel.html/css/js — the side panel UI
- tokens.css — the desk's paper/olive token set (light + dark), hard corners,
  JetBrains Mono. Kept as a deliberate copy so the extension has zero
  runtime dependency on the dashboard's CSS; when palette.css changes,
  mirror the token values here.

## Rules it enforces

- Read-only: GET /state/*.json only, public-safe files only. Never touches
  config/desk.json, vetted/audited/proposed outputs, or any broker system.
- Health gate client-side: signals.json entries render degraded when
  health.status != "ok" (build_signals.py does not check this itself).
- No advice language, no entry/stop/target on named tickers, no orders.
- Inert to deploys: vercel_build.sh copies dashboard/ and state/ only;
  this folder never ships to Vercel.
