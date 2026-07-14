# PSX Trade Desk — Operations Runbook

**Read this before touching anything that reaches the live site.** It is the single source of truth
for how the desk runs, who does what, and how to publish without breaking the live website. Governance
rules (position sizing, circuit breaker, no-lookahead, etc.) live in [`CLAUDE.md`](../CLAUDE.md); this
doc is about *operations*.

Live site: https://psx-trade-desk.vercel.app/ · Repo: private, hosted on Vercel · Auth/DB: Supabase.

---

## 1. The hybrid architecture (who runs what, where)

Two halves, on purpose. The split is what gives 24/7 freshness at controlled token cost.

```
COMPUTER OFF — GitHub Actions cloud cron  (.github/workflows/desk-data.yml)   FREE, no tokens, no agents
  every 30 min off-peak, market hours →  python scripts/run_cloud.py
  = prices · quant · backtests · fair value · health · dashboard
    + Desk Room DETERMINISTIC scaffolding (dossiers · queue · gate · scoring)
  → publish.py → push → Vercel deploy → watchdog

COMPUTER ON — app scheduled tasks (Claude app, ~/.claude/scheduled-tasks/)     tokens, owner present
  the JUDGEMENT/agent work: news-sentinel · monitor · macro · daily read
  · the Desk Room DEBATES (chartist/fundamentalist/bull/bear/chair) · weekly broker harvest
  → publish.py → push → Vercel deploy → watchdog

ALWAYS — every visitor sees the full SAVED analysis 24/7 (debates, TA/FA, 52 backtests, scores),
  because agent output is persisted in state/ and served statically. Agents REFRESH it; they are
  not needed for a user to READ it. Nothing goes dark when the computer is off.
```

**Rule of thumb:** deterministic/data work can run in the cloud; anything that needs Claude (an agent)
runs on the owner's machine. The cloud never runs an agent (no API key by design).

---

## 2. The ONE publish path — never hand-push state

**Always publish with `python scripts/publish.py "<message>"`. Never `git push` state files by hand.**

`publish.py` is the shared choke point every loop and the cloud use. It:
1. runs `preflight.py` (the pre-deploy gate) — **if it fails, nothing publishes**, last-good site stays live;
2. stages, and commits **only if state actually changed** (a no-op otherwise);
3. pushes **race-safely** — the cloud cron and app loops both push to `main`, so on a rejected
   (non-fast-forward) push it rebases onto latest preferring our fresh state (`-X theirs`) and retries.
   Whatever the other side raced in regenerates next cycle, so nothing is lost.
4. A push to `main` is the entire deploy — Vercel auto-builds in ~60s. There is no separate deploy step.

---

## 3. The safety gates (why the live site doesn't break)

Layered, so a bad cycle can't reach users and a transient glitch can't blank a page:

- **`preflight.py`** (before publish): re-reads every file the UI joins on; asserts shape, non-empty,
  no NaN/Infinity, and **per-ticker history completeness** (the "No data for XXX" class). Exits non-zero
  → `publish.py` aborts.
- **`watchdog.py`** (after publish): fetches the LIVE Vercel URLs a browser hits and checks they are
  reachable, fresh, non-empty, health not degraded, and sampled ticker histories serve. Wired into every
  publishing loop; if it fails, the loop re-publishes once then reports loudly. Run ad hoc:
  `python scripts/watchdog.py`.
- **`data_health.py`** (Rule 6): if `health.json.status != ok`, NO new signals generate that cycle
  (monitoring continues). `tv_crosscheck` feeds it but only a **genuine glitch** (close off >12% =
  decimal/split/wrong-symbol) degrades health; TV lag/adjustment **drift** is advisory and never freezes
  the desk (a TV-vs-DPS mismatch is not an error — CLAUDE.md).
- **Client resilience** (in `app.js`): `j()` retries + XHR fallback + last-known-good; a router try/catch
  never leaves a blank screen; a 30-second auto-refresh self-corrects transient misses; the ticker page
  self-heals with retry.

---

## 4. The six app scheduled tasks (`~/.claude/scheduled-tasks/`)

Only run while the Claude app is open; catch up on next open. Each ends with `publish.py` + watchdog.
The cloud cron now keeps DATA fresh 24/7, so these are primarily about the **agent** work — but they
still run `run_cloud.py` first (cheap, idempotent) as a local-freshness prereq and a cloud-outage fallback.

| Task | When (PKT) | Does |
|---|---|---|
| `psx-desk-hourly-cycle` | **Mon–Thu 10:00 & 16:00** (open+30 / close+30) | data + **news-sentinel** + position **monitor**; escalates to full commentary only on impact ≥ 4 news |
| `psx-desk-checkpoint-fri-mid` | **Fri 09:47 & 14:47** (open+30 / post-break+15) | same flow as above — see §4a |
| `psx-desk-checkpoint-fri-close` | **Fri 17:00** (close+30) | same flow as above — see §4a |
| `psx-desk-daily-refresh` | weekday ~17:20 | macro + market-analyst **daily read** (≤120 words) |
| `psx-desk-room-loop` | weekday ~17:47 | the **Desk Room debates** — ≤3 full/day (budget gate), rest reaffirm free; QA + scoring |
| `psx-desk-weekly-harvest` | Sat ~11:00 | broker **calls** from the business press (Profit/Dawn/Mettis) + filings refresh |

Manual refresh (any session, no waiting for a task): the **`update-live-desk`** skill, or directly
`python scripts/run_cloud.py` (free data) then `python scripts/publish.py "..."`.

### 4a. Market-event checkpoints, not hourly (changed 2026-07-14)

`psx-desk-hourly-cycle` no longer runs hourly — it fires only at real PSX market events (open, Friday's
break-end, close), for token efficiency. Because a single cron expression can't hold multiple distinct
(hour, minute) pairs, this needed **3 separate scheduled tasks**, all pointing at the **same**
`psx-desk-hourly-cycle/SKILL.md` (the two Friday tasks' own prompts just say "read and execute that file
verbatim"). **To change checkpoint behavior, edit only `psx-desk-hourly-cycle/SKILL.md`** — the other two
tasks have no independent logic. Times are rounded to the nearest 5 min for a shared cron minute field
(e.g. 10:02→10:00); the scheduler already adds several minutes of dispatch jitter on top, so this is well
within existing tolerance. Note: the scheduler's human-readable `schedule` summary string is buggy for
multi-value hour fields (shows only the first value/weekday) — trust `cronExpression` and `nextRunAt` from
`list_scheduled_tasks`, not the summary text.

---

## 5. The cloud workflow — editing gotcha

`.github/workflows/desk-data.yml` runs the deterministic pipeline in the cloud.
**You cannot push changes to `.github/workflows/*` from this environment** — the git credential and `gh`
here lack GitHub's `workflow` OAuth scope. To add/edit it, use the **GitHub web UI** (repo → Actions →
edit the workflow → commit), or have the owner grant the scope. After a web edit, `git pull` to sync local.
Also ensure repo **Settings → Actions → General → Workflow permissions = Read and write** (so the job can
push refreshed data).

---

## 6. Hosting & data ownership

- **Vercel** serves the static site from committed files (`vercel.json` copies `dashboard/*` + `state/`
  into `public/`). Push to `main` = deploy. `Cache-Control: must-revalidate` is set, so users get fresh
  JS/CSS after each deploy (no stale-cache class on live; the local `serve.py` preview DOES cache — hard-
  reload it when testing).
- **Supabase** = auth + per-user data ONLY (never serves research data). Per-user, row-level-secured on
  the `profiles` table: `watchlist`, `notes`, `portfolio`, `followed_brokers`, `digest_prefs` (all jsonb).
  The client uses the publishable key (safe); the legacy service_role/anon keys are disabled.
- **Repo is private.** State data (incl. `history/`, `history_deep/`, `intraday/`) is committed so Vercel
  is self-contained.

---

## 7. Universe coverage — what tickers the desk tracks

`config/desk.json.universe` controls this. As of 2026-07-14: **full KSE100 (100) + full KMI30 (30),
deduped ≈ 103 symbols** (`kse100_top_n: 100`). This was previously capped at `50` — top-50-by-weight only
— which silently excluded real constituents (e.g. KAPCO, KSE100 rank #75) from search, the Board, and
every page. If a ticker a user searches for is a genuine index constituent and still doesn't appear,
check `state/universe.json.symbols` first (is it there?), then `config/desk.json.universe.kse100_top_n`
(was it capped again?) — don't assume it's a search bug.

**Cost note:** the deterministic layer (prices/quant/backtests) is free regardless of universe size —
more tickers just means more (free) compute time. Only the Desk Room **debates** are token-budgeted
(`deep_dives_per_day` in the Room config), and that budget is independent of universe size — a bigger
universe means the coverage queue is longer, not that any single cycle spends more tokens.

**Backfill note:** widening the universe requires a one-time full run of `run_cloud.py` (fetches history/
deep-history/fundamentals for the newly-added tickers — subsequent runs are fast again since
`fetch_deep_history.py` only pulls missing tickers). If done via the cloud cron, the first run may run
long; the 15-min timeout in `desk-data.yml` may need raising to ~25 min for that one run (web-UI edit
required — see §5). Preflight/publish gating means a timeout never publishes broken state either way —
worst case the backfill just continues on the next scheduled run.

---

## 8. Known gaps / honest notes

- **Sector concentration** in the portfolio tracker is by POSITION, not sector — the feed only has numeric
  sector codes (e.g. `0809`), no names. Building a code→name map would enable true sector grouping.
- **Digest email SENDING** is not wired (prefs are captured in `digest_prefs`). Needs an email provider
  (e.g. Resend) + a scheduled loop. On hold per owner.
- **Legal pages** (`state/legal.json`, `#/legal/*`) are DRAFTS — a Pakistani lawyer must review before
  charging (flagged in the file's `review_status`). Discoverable from: page footer, the sidebar bottom
  (`.side-legal`), the sign-in/sign-up modal (`.auth-legal`), and the Settings page.
- **Track record** is young (see the clock on the Scores page). Do not switch on paid billing until it
  matures — that clock is the honest gate.

---

## 9. Fixed bug class — `hidden` attribute silently overridden by CSS

The account-menu dropdown never actually closed (2026-07-14): `menu.hidden = true` was set correctly in
JS, but `.acct-menu{display:flex}` (an author-stylesheet class rule) unconditionally overrode the
browser's native `[hidden]{display:none}` default — author-origin CSS always wins over the UA default,
regardless of selector specificity. The element was visually always-open from the moment it was first
rendered; the JS toggle was a no-op the whole time. Proven with `getComputedStyle(el).display` while
`el.hidden = true`. Fixed with an explicit `.acct-menu[hidden]{display:none!important}` override — the
same pattern already used for `.searchbox[hidden]`.

**Rule going forward: any element toggled via the `hidden` DOM property MUST have a matching
`.class[hidden]{display:none!important}` CSS rule**, or the toggle silently does nothing. Checked
2026-07-14: only two such elements exist (`#searchbox`, `#acctMenu`), both now correctly overridden.

---

## 10. If the live site looks wrong — triage order

1. `python scripts/watchdog.py` — is it stale, degraded, or serving empty? It tells you which.
2. If **degraded**: read `state/health.json.problems`. A `tv_crosscheck ERROR` = a real data glitch;
   `drift` in `advisories` = benign TV lag (ignore).
3. If **stale** (`updated` old): a deploy didn't propagate or no cycle ran — run `run_cloud.py` +
   `publish.py`, or trigger the cloud workflow (Actions → Run workflow).
4. If a **single ticker** is blank: check `state/history/<SYM>.json` exists and is non-empty; preflight
   should have caught a broad gap. The client self-heals transient misses (retry button/auto-retry) — a
   one-off "couldn't load" that clears on retry is normal transient behavior, not a data bug.
4b. If a user reports **every ticker / all pages** blank at once, but `curl`ing the live state files and
   `watchdog.py` both show healthy 200s with real data: this is almost always CLIENT-side — either (a) a
   browser extension (ad/anti-fraud blocker) monkey-patching `window.fetch` and throwing on same-origin
   requests (the reason `j()` in app.js has an XHR fallback), or (b) the user was on the page during the
   ~60s Vercel deploy-propagation window right after a publish. Verify server-side health FIRST (curl the
   state files + `watchdog.py`) before assuming a data bug — don't guess from a screenshot alone. Ask the
   user to hard-refresh or try a different browser/incognito if it's reproducible.
5. If a ticker can't be **found in search**: see §7 — check it's actually a tracked constituent before
   assuming a search bug.
6. Never fix by hand-pushing — fix the data, run `publish.py`, let the gates pass.
7. **Whenever you change something structural** (universe size, a config default, a new per-user table, a
   new loop) — update this file (`docs/OPERATIONS.md`) and, if it affects a scheduled task's behavior, that
   task's `SKILL.md` in the same turn. Docs going stale is how future sessions break things they don't
   know changed.
