# The Desk Room — Multi-Agent Analyst Loop for Henneth

Status: PROPOSED (awaiting owner approval). Written 2026-07-13.
Goal: make this the best investing research platform in Pakistan — named AI analysts that
research, debate, and publish a house view per ticker, covering TA and FA separately,
digesting broker reports and AGM/quarterly briefings, on a token budget.

---

## 1. Reference models (what already works internationally)

| Platform / paper | What we take from it |
|---|---|
| **TradingAgents** (UCLA/MIT, arXiv 2412.20138) | The core architecture: specialist analysts (fundamental / technical / news / sentiment) → **bull-vs-bear researcher debate** → trader → risk governance. Their key token trick: **hybrid protocol** — agents exchange compact structured summaries; free-form debate only where reasoning adds value. Bounded debate rounds. |
| **Seeking Alpha Virtual Analyst Reports** (2026) | AI persona reports that synthesize quant + news + analyst opinion per ticker. Proof the "named AI analyst" product works commercially. |
| **TipRanks** | Analyst **track records** drive trust. Every persona call is dated, falsifiable, and scored later — a public leaderboard. |
| **Simply Wall St** | Visual, plain-English FA (the "snowflake"). We already do scorecards; the Room adds narrative on top. |
| **Morningstar** | Fair value + **uncertainty/conviction rating** attached. House view always carries conviction + explicit dissent. |
| **Atlantis / fiscal.ai** | Earnings-call & filing digestion: transcript in → structured summary (tone, guidance, risks, Q&A highlights) out. Our "Librarian" layer. |

Nobody does this for PSX. That's the moat.

---

## 2. Token-efficiency doctrine (the #1 constraint)

1. **Deterministic Python does everything repeatable.** Agents never fetch or compute — they judge. (Existing desk rule; unchanged.)
2. **Dossier-first.** Before any agent runs, `build_dossier.py` compiles a compact per-ticker
   dossier (~1–2k tokens) from state files: price/quant summary, proven strategies, fair value
   working, scorecard, dividends, tagged news, latest filings digests. Agents read the dossier,
   never raw files. One compilation, many readers.
3. **Bounded debate.** Bull and Bear get exactly one case + one rebuttal each, ≤250 words per turn,
   structured JSON out. No open-ended loops.
4. **Rotation, not blanket coverage.** 2–3 deep dives/day, queue-ordered. 60 tickers ≈ full
   universe refreshed every ~4 weeks, and event triggers jump the queue so nothing important waits.
5. **Digest once, cite forever.** Every PDF (broker note, AGM deck, results) is digested ONCE by a
   cheap model (Haiku) into ≤300 words, keyed by document hash, cached in state. Personas quote
   digests, never re-read PDFs.
6. **Right-size the model per role.** Librarian/digestion → Haiku. Debate + Chair synthesis →
   Sonnet. (Agent frontmatter `model:` field.)
7. **Delta-aware.** A re-visit only re-runs personas if the dossier materially changed
   (hash of key fields); otherwise the previous Room stands with a "reaffirmed" stamp — near-free.
8. **Hard budget.** `state/budget.json`: max deep dives/day, max escalations/day, monthly token
   estimate. Circuit breaker: budget hit → queue pauses, monitoring continues.

**Cost estimate:** deep dive = 6 agent calls × (1.5k in + 0.4k out) ≈ 15–25k tokens.
3/day ≈ 50–75k tokens/day ≈ well inside a Max plan alongside existing routines.

---

## 3. The personas (named AI analysts — disclosed as AI, never advice)

TA and FA are **separate desks with separate state files** — they never blend memos.

| Persona | Role | Reads | Writes |
|---|---|---|---|
| **Meher — The Chartist** (TA desk) | Pure technicals: trend, momentum, S/R, volume, what the proven strategies say NOW | dossier §quant, §backtests, §strategy_map | `state/room/{SYM}.json → ta_memo` |
| **Dr. Omar — The Fundamentalist** (FA desk) | Pure fundamentals: earnings quality, valuation vs peers, dividend safety, balance-sheet flags | dossier §fundamentals, §fairvalue, §scorecard, §filings digests | `→ fa_memo` |
| **Zoya — The Bull** | Strongest honest case FOR, must cite both memos | ta_memo + fa_memo + dossier | `→ bull_case` |
| **Khurram — The Bear** | Strongest honest case AGAINST, must attack the bull's weakest link | same + bull_case | `→ bear_case` |
| **The Chair** | Synthesizes: house view, conviction (high/med/low), explicit dissent line, 1–3 dated falsifiable expectations | everything above | `→ house_view` |
| **The Librarian** (Haiku) | Digests documents: broker notes, AGM/briefing decks, results announcements → structured 300-word summaries | raw PDFs/text | `state/research/{dochash}.json` |

Rules for all: numbers only from the dossier or a cited digest. No advice language — output is
"the desk's read." Every expectation is dated and falsifiable ("expects X by DATE") so it can be
scored. Persona cards in the UI carry the label **"AI analyst persona — research, not advice."**

Existing agents unchanged: strategist still owns setups, risk-officer sizes, **auditor still vetoes**.
The Room informs the strategist (its dossier includes the latest house view); it never places setups.

---

## 4. The coverage loop

**Queue order (rebuilt daily, deterministic):**
1. Results/AGM/briefing in next 7 days (from earnings_calendar)
2. Impact ≥ 4 news since last Room visit
3. New signal fired / auditor-passed setup
4. New document landed (broker note or filing mentioning the ticker)
5. Stalest Room entry first (guarantees full-universe rotation)

**Cadence:**
- **Daily (rides existing 17:20 PKT task):** top 2–3 of queue get a full Room session.
- **Hourly (rides existing hourly task):** no Room sessions — but if news-sentinel logs impact ≥ 4,
  the ticker jumps to tomorrow's top slot, or triggers an immediate single Room session if markets
  are open (counts against escalation budget).
- **Weekly:** self-improvement pass (see §6).

---

## 5. Broker reports, AGMs, quarterly briefings (the Librarian layer)

Deterministic fetchers (free):
- **PSX announcements** — results, board meetings, corporate briefing session (CBS) decks. Companies
  must file CBS presentations to PSX; these are the AGM/quarterly-meeting material. `fetch_filings.py`.
- **Public broker research** — AKD Daily, Topline Morning Shot, JS morning notes etc. publish free
  PDFs daily. `fetch_broker_notes.py` (respect robots; only public docs).
- **Financial trends** — extend `fetch_fundamentals.py` to pull multi-year revenue/earnings/margins/
  debt + company description from stockanalysis.com (fills the known data gap; enables the
  "How has the business performed?" charts already spec'd).

Pipeline: fetch → pypdf text extract → hash → Librarian digest (once) → tagged to tickers →
appears in dossiers + a new **Research** tab. When a broker's view disagrees with the desk's house
view, the Chair must address the divergence explicitly in the next Room session — that's the
"agents give opinions on broker reports" feature, grounded.

### 5b. Brokers are AUDITED, never trusted (core principle)

A broker note is **evidence to be cross-examined, not an answer.** Owner's rule: brokers miss things,
carry sector/house bias, talk their book, and are often simply wrong. So:

1. **Every broker note enters the debate as a claim to attack, not a conclusion.** The Librarian
   extracts each note's concrete, falsifiable claims (target price, rating, thesis, catalyst, date).
   Zoya may use a bullish broker claim as support — but Khurram is explicitly tasked to **stress-test
   it**: what did the broker omit, what's their incentive, where's their history weak in this sector?
   The Chair's house view must state whether it **agrees, partially agrees, or rejects** each broker
   claim, with reasoning — never "AKD says buy, so."
2. **Broker scorecard (deterministic, free).** Every extracted broker claim is dated and later scored
   against what actually happened (price vs target by the target's own horizon; rating direction vs
   subsequent return). Rolls up into `state/broker_scorecard.json`:
   - per broker: overall hit rate, avg target error %, directional accuracy, sample size
   - **per broker × sector** (banks / E&P / cement / fertilizer / tech / power …) — because each broker
     staffs sector-specialist desks with very different track records. A broker strong on banks may be
     weak on E&P; the scorecard captures that granularity.
   - recency-weighted, with a "too few calls to rank" floor so we never over-trust a small sample.
3. **Weighted, not ignored.** In the dossier, each broker claim is annotated with that broker's
   **sector-specific track record** ("Topline on cement: 61% directional, avg target error 12%, n=14").
   Personas weight a claim by the source's proven reliability in THAT sector — a strong-record call
   carries more; a weak-record call is treated as a weak prior. Nobody is taken at face value.
4. **Public broker leaderboard** (see §6/§7): brokers ranked overall and by sector, most-to-least
   reliable, with their best and worst calls surfaced. This is itself a differentiator — no PSX
   platform grades the brokers.

The same claim-extraction + scoring machinery runs on **our own personas** (§6.1), so the desk holds
itself to the identical standard it holds the brokers to.

---

## 6. Self-improvement loops (three, mostly free)

1. **Call scoring (free, Python).** Every dated expectation from every persona is checked nightly
   against subsequent prices/events → `state/leaderboard.json`. Each persona's future prompts
   include their own hit rate and last 3 misses — TipRanks-style accountability, and it measurably
   sharpens outputs. Reviewer agent turns misses into numbered lessons (existing learnings loop).
2. **Debate quality audit (weekly, 1 agent call).** Reviewer grades last week's Rooms: did the Bear
   flag what actually went wrong? Were numbers all sourced? → prompt adjustments logged in
   `docs/room-tuning.md`.
3. **Platform PM loop (weekly, 1 agent call).** A "Product" pass reads the backlog + latest desk
   state + this plan and proposes ≤3 platform changes — ADD (new data, new view) or **SIMPLIFY**
   (remove/merge clutter) — into `state/backlog.json`. Owner approves items in chat; they get built
   in normal sessions. This is the "keep improving the platform" loop, with a human gate.

---

## 7. UI additions

- **Ticker page → "The Desk Room" section:** TA memo and FA memo side-by-side (separate, as
  required), then the debate thread (Zoya vs Khurram), then the Chair's house view with conviction
  meter + dissent line + dated calls (each stamped pending/hit/miss). Persona avatars = initials in
  terminal boxes; AI-persona disclaimer on the section.
- **Research tab:** digests library — broker notes + CBS/AGM decks + results, filterable by ticker,
  each linking to source doc; "broker vs desk" divergence flags.
- **Leaderboard page:** two boards, same scoring engine — (a) our persona track records, (b) the
  **broker leaderboard** ranked overall and by sector (hit rate, avg target error, best/worst call).
  Broker board is the public-facing differentiator: "here's who's actually been right on PSX."
- **Today tab:** yesterday's Room sessions summarized (1 line each).

---

## 8. Build phases

| Phase | What | Cost profile |
|---|---|---|
| **0. Foundations** | build_dossier.py, fetch_filings.py, fetch_broker_notes.py, fundamentals-trends scraper, call-scoring engine, budget.json | All deterministic — zero tokens |
| **1. Pilot** | 6 persona agent files, Room schema, run ONE ticker end-to-end (FFC), render Desk Room UI, measure real token cost | ~1 deep dive |
| **2. Loop** | Queue builder + wire into daily task (2–3 dives/day) + hourly escalation hook | Daily budget |
| **3. Librarian** | Document pipeline + Research tab + broker-divergence rule | Haiku-cheap |
| **4. Accountability** | Leaderboard + scoring nightly + reviewer/PM weekly loops | ~2 calls/week |
| **5. Polish** | Simplification pass, mobile, disclaimer review, then consider public launch | — |

Each phase ships independently; the desk keeps running throughout. Preflight gate extends to the
new state files so a broken Room never deploys.

---

## 9. Open decisions for the owner

1. Persona names/genders — placeholders above; rename freely.
2. Deep dives per day: 2 (leaner) or 3 (faster full-universe rotation)?
3. Broker sources to include (AKD/Topline/JS confirmed public; add others?).
4. Leaderboard public on the site, or owner-only at first?
