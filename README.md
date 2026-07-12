# PSX Trade Desk

Personal multi-agent trading intelligence desk for the Pakistan Stock Exchange.
Researches, scores, backtests, and monitors signals. **Never places orders** — execution
is manual on your broker app. Desk rules live in `CLAUDE.md` (every agent inherits them).

## Architecture

```
run_desk.ps1 (Task Scheduler, every 30 min, market hours)
   ├── full cycle (first run of day):  prompts/cycle-full.md via claude -p
   │     Python: universe → history → quant → predictability → backtest → snapshot → health
   │     Agents: news-sentinel + macro → strategist → risk-officer → auditor → monitor → report
   └── light cycle (intraday):         prompts/cycle-light.md via claude -p
         Python: snapshot   Agents: news-sentinel → monitor → report
         (escalates to full cycle on impact ≥ 4 news)

state/*.json  →  dashboard (localhost:8877)  +  Telegram alerts
```

Deterministic math = Python (`scripts/`). Judgment = agents (`.claude/agents/`).
Auditor re-derives every approved setup from raw data and vetoes mismatches.

## Runbook

```powershell
# one-off deterministic pipeline (no agents, no tokens)
python scripts\update_universe.py     # weekly
python scripts\fetch_history.py       # daily pre-market
python scripts\quant.py
python scripts\predictability.py
python scripts\backtest.py
python scripts\data_health.py
python scripts\snapshot.py            # any time during market hours
python scripts\tv_crosscheck.py       # verify quant vs TradingView (--all for full sweep)

# reference layer (dividends, fundamentals, earnings calendar)
python scripts\fetch_dividends.py     # daily pre-market (DPS book closures)
python scripts\fetch_fundamentals.py  # weekly (stockanalysis.com: P/E, EPS, mktcap, earnings dates)
python scripts\build_calendar.py      # normalizes earnings + ex-div into earnings_calendar.json

# global markets that drive PSX (crude, S&P, Dow, VIX, gold, BTC, ETH, USD/PKR, DXY)
python scripts\fetch_global.py        # every cycle (Yahoo Finance, no login)
python scripts\fetch_georisk.py       # geopolitical & market-stress radar (after global + newslog)
python scripts\score_fundamentals.py  # plain-English financial scorecards
python scripts\build_dashboard.py     # assemble state/dashboard.json (regime, geo, movers, news)

# ONE-TIME deep history backfill (~19y OHLC from Yahoo .KA; DPS caps at 5y)
python scripts\fetch_deep_history.py  # run once; --refresh to re-pull

# dashboard (SPA: Board · Macro · Dividends · Earnings · News · ticker detail — Gemini, single theme)
python scripts\serve.py               # → http://localhost:8877/dashboard/app.html

# manual full cycle (this is the "clean run" test)
powershell -ExecutionPolicy Bypass -File scripts\run_desk.ps1 -Full

# arm the 30-min loop (ONLY after 5 clean manual runs)
powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
# disarm
Unregister-ScheduledTask -TaskName "PSX Trade Desk" -Confirm:$false
```

## Before going live — owner TODO
1. `config/desk.json`: set real `capital_pkr`.
2. Telegram: create bot via @BotFather, paste `telegram_bot_token` + `telegram_chat_id`.
   (Until then alerts only log to `state/alerts.json`.)
3. Verify `state/calendar.json` holidays against official PSX notices.
4. 5 clean manual full-cycle runs, then register the scheduled task.
5. **Paper month**: 4 weeks, zero real trades, gate = 20+ signals, ≥60% win rate,
   realized R ≥ 1:1.5, zero Auditor misses.

## Data notes
- Source: PSX DPS portal (unofficial). EOD feed = `[ts, close, volume, open]` — **no high/low**,
  so `atr14_proxy` is close-to-close. True intraday OHLC accumulates in `state/ohlc_daily/`
  from market-watch snapshots.
- `data_health.py` gates signal generation: stale/broken data → no new setups.
- Backtest eligibility: n ≥ 8 trades, hit rate ≥ 55%, net expectancy ≥ 0.5% after 0.6% friction.
- Second source: `tradingview-ta` (pip) hits TradingView with screener='pakistan', exchange='PSX'.
  `tv_crosscheck.py` compares close/RSI/SMA20/SMA50 vs our quant layer; any FAIL blocks signals
  and is an Auditor veto ground. (The tradingview-mcp server itself isn't used — its screeners
  and backtester don't cover PSX; the library underneath is the useful part.)
