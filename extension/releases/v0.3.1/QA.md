# Release QA — v0.3.1

Date: 20 August 2026

## Automated checks

- `node --check extension/panel.js` — passed
- `node --check extension/background.js` — passed
- `scripts/check_rule4.py` — passed (7 Rule 4, 5 payout, 14 symbol cases)
- `scripts/preflight.py` — passed
- ZIP manifest — `manifest_version: 3`, version `0.3.1`
- ZIP contents — 14 runtime files; no `node_modules/` or `src/`
- SHA-256 checksum — verified against `SHA256SUMS.txt`

## Expected Chrome smoke test

1. Load the ZIP or unpacked release in `chrome://extensions`.
2. Open a supported TradingView, PSX DPS, or news page.
3. Open the Henneth side panel while signed out; confirm the account-connection card appears.
4. Confirm **Sign in** and **Create free account** open the correct Henneth auth pages.
5. Sign in, reopen the panel, and confirm the ticker read loads.
6. Confirm Ask and Notes become available after the session token is received.

## Preflight note

The gate reported one non-blocking backfill warning for newly added universe tickers. It does not block publishing by design.
