# Henneth — System Registry

The single index of every moving part, so the whole system can be recalled cheaply instead of
re-derived. If you build a new agent, loop, or script, add one line here. Last updated 2026-07-14.

Cost model: **deterministic Python = free** (no tokens, runs in the cloud/cron). **Agents = tokens**
(only run on a schedule or on escalation, right-sized model). The whole design is "free layer does the
heavy lifting; agents only judge, only when something changed."

---

## Loops (scheduled tasks — the automation)

| Task | Cadence | Cost | What it does |
|---|---|---|---|
| `psx-desk-hourly-cycle` | weekdays hourly, mkt hours | cheap | run_cloud + news-sentinel + monitor; escalates on impact≥4 |
| `psx-desk-daily-refresh` | weekdays 17:20 PKT | ~3 agents | macro + analyst read + news; GH-Actions self-heal nudge |
| `psx-desk-room-loop` | weekdays 17:47 PKT | ≤3 debates | Desk Room: reaffirm free / delta cheap / full debate (gated) + verifier QA + persona scoring |
| `psx-desk-weekly-harvest` | Sat 11:00 PKT | 1 haiku agent | broker-call harvest (Profit/Dawn/Mettis) + filing refresh + score |
| Cloud GitHub Actions | 30 min cron + on push | free | full deterministic pipeline (run_cloud steps) → deploy |

(Tweet/content tasks `psx-*-tweet`, `psx-burst-*` are a SEPARATE content system, not the desk.)

## Agents (`.claude/agents/*.md`)

**Desk core (original 9):** `strategist` (setups) · `risk-officer` (sizing) · `auditor` (veto) ·
`monitor` (positions) · `news-sentinel` (news) · `macro-agent` (regime) · `market-analyst` (daily read)
· `fundamentals-agent` (reference) · `reviewer` (lessons).

**The Desk Room (analyst debate, per ticker):**
- `room-chartist` (Meher, TA-only, sonnet) · `room-fundamentalist` (Dr. Omar, FA-only, sonnet)
- `room-debate` (Zoya bull + Khurram bear in ONE call, sonnet) — replaces separate bull/bear
- `room-chair` (house view + conviction + dissent + dated calls, sonnet)
- `room-librarian` (digests filings/notes once, haiku)
- `room-verifier` (adversarial fact-check QA, web-verifies, can block, sonnet)
- `room-broker-harvester` (weekly broker-call capture from press, haiku)
- (`room-bull`/`room-bear` exist but are superseded by `room-debate`)

**Design/UI:** `design-reviewer` (enforces the locked design language + typography hierarchy, sonnet).

## Deterministic scripts (`scripts/` — free layer)

- Data fetch: `fetch_history`, `fetch_deep_history` (+ de-glitch cleaner), `fetch_intraday`,
  `fetch_global`, `fetch_georisk`, `fetch_dividends`, `fetch_fundamentals`, `fetch_research`,
  `fetch_broker_calls`.
- Desk Room layer: `room_dossier` (compact per-ticker dossier — agents read THIS) · `room_queue`
  (coverage rank) · `room_gate` (tier: reaffirm/delta/full) · `room_score` (persona+broker leaderboards)
  · `room_verify` (QA) · `room_apply` (assemble a session) · `room_broker_apply` (record broker calls).
- QA gates: `preflight` (blocks a broken deploy) · `design_lint` (UI/typography drift).
- Orchestration: `run_cloud` (runs the whole free pipeline in order).

## Skills (`.claude/skills/`)

- `update-live-desk` — refresh the live site (Path A free cloud trigger vs Path B token agents).

## Key state files (`state/`)

`dashboard.json` (board core) · `quant/predictability/backtests/strategy_map` (TA) ·
`fairvalue/fundamental_scores/fundamentals` (FA) · `dossiers` (Room input) · `rooms` (Room sessions) ·
`claims` (dated calls ledger) · `leaderboard`+`broker_scorecard` (track records) ·
`research_index` (filings + broker notes) · `verify`+`design_lint` (QA) · `room_queue`+`room_plan`+`budget`
(cadence/cost) · `health`+`calendar` (gates).

## The three self-checking systems (all two-layer: free lint + agent judgment)

1. **Data QA** — `room_verify.py` (free) flags glitchy/inconsistent numbers → `room-verifier` agent
   web-checks + can block. Fixed the "UBL 83%" class of bug.
2. **Deploy QA** — `preflight.py` gates `build_dashboard`; a structurally broken cycle can't publish.
3. **Design QA** — `design_lint.py` (free) flags corner/padding/token/typography drift → `design-reviewer`
   agent fixes surgically. Enforces the locked design language.

## Locked rules (never break)
- Long-only, daily-timeframe, research NOT advice, every number from the data layer (CLAUDE.md).
- UI: hard corners (radius 0), boxes 1.5px solid var(--line), colors from tokens, cards pad children 12px,
  tight type scale, JetBrains Mono uppercase labels + Pixelify for hero numbers.
- Brokers are audited, never trusted — every broker call is scored on the leaderboard.
- The auditor keeps veto; the Room only informs the strategist.
