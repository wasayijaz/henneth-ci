# Weekly sector debate — one sector per run

Runs once a week (Saturday, after the broker harvest). Debates **one** PSX sector so the token
cost is bounded and predictable: with 13 sectors in the dossier, every sector is covered roughly
once a quarter, and the rotation is deterministic rather than whatever looks interesting today.

## Steps

1. **Refresh the evidence pack (free, no tokens):**

   ```bash
   python scripts/sector_dossier.py
   ```

   This rebuilds `state/sector_dossiers.json` from the desk's own state files. If it reports fewer
   than 3 sectors, stop — the data layer is incomplete and a debate would be built on sand.

2. **Pick this week's sector — deterministically, not by taste.** Read
   `state/sector_debates/_rotation.json` (create it as `{"queue": [], "done": []}` if missing).
   - If `queue` is empty, refill it with every sector key in `sector_dossiers.json`, ordered by
     `n_members` descending, so the sectors that affect most of the universe come first.
   - Take the first sector off `queue`.
   - **Jump the queue only for a real reason:** any sector holding a ticker with an impact ≥4 news
     item in the last 7 days (check `recent_news` in the dossier) goes first. Note in the output
     that it jumped, and why.

3. **Run the debate** — Task tool, `subagent_type: "sector-debate"`, telling it which sector.
   It writes the bull case, bear case and rebuttal to
   `state/sector_debates/<sector-slug>.json`.

4. **Run the Chair** — Task tool, `subagent_type: "sector-chair"`, same sector. It adds
   `house_view` with stance, conviction, mandatory dissent, and dated market-relative claims.

5. **File the claims for public scoring.** Append each `house_view.claims` entry to
   `state/claims.json` in the same shape the desk uses elsewhere: `source_type: "desk"`,
   `source: "sector-desk"`, the sector in `tickers` as `["SECTOR:<name>"]`, `market_relative: true`,
   and a `benchmark` stamped with the current KSE100 level from `state/indices.json`. A
   market-relative claim without a stamped benchmark cannot be graded honestly later.

6. **Update the rotation:** move the sector from `queue` to `done`, write `_rotation.json`.

7. **Publish:**

   ```bash
   python scripts/publish.py "Sector debate: <Sector> — <stance>, conviction <level>"
   ```

## Cost

One `sector-debate` call (both sides in a single pass) plus one `sector-chair` call per week.
Two agent calls, once a week — bounded and predictable by design. Do **not** loop over sectors:
the whole point of the rotation is that the weekly cost never scales with the number of sectors.

## Hard rules

- Both agents cite `sector_dossiers.json` only. No figure from memory (CLAUDE.md Rule 2).
- No advice language anywhere in the output (Rule 5).
- Dissent is mandatory in the house view. A session without real dissent is a failed session.
- If `state/health.json` is not `ok`, still run: this is analysis of existing data, not a new
  trading signal. But note the health status in the session so a reader knows the data was degraded.
