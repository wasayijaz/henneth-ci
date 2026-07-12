# Deploying the PSX Trade Desk — free cloud (data desk)

Architecture (all free tiers):

```
GitHub Actions (cron every 30 min, market hours)  ──runs the Python pipeline──▶
Supabase Storage (public bucket 'desk', JSON)     ◀──reads──  Vercel (static dashboard)
```

No LLM agents run in the cloud, so there is **zero token cost**. The cloud shows the
deterministic desk: charts, 52 strategies, scorecards, geo-risk, dividends, calendar,
macro/global. (The agent commentary — daily read, news tagging, signals — stays on your
PC; run those locally and they get pushed to Supabase too.)

Already done for you: Supabase project `qteoncckohuoatbjjykb`, public bucket **desk**,
and the dashboard is wired to read from it when not on localhost.

## 1. Put the repo on GitHub
```powershell
cd "D:\PSX Trader X Claude"
git init && git add -A && git commit -m "PSX Trade Desk"
# create a repo on github.com (public = unlimited free Actions minutes), then:
git remote add origin https://github.com/<you>/psx-trade-desk.git
git push -u origin main
```

## 2. Add two GitHub secrets
Repo → Settings → Secrets and variables → Actions → New repository secret:
- `SUPABASE_URL` = `https://qteoncckohuoatbjjykb.supabase.co`
- `SUPABASE_SERVICE_KEY` = your **service_role** key
  (Supabase dashboard → Project Settings → API → `service_role` secret. This is the ONLY
  key that may write to Storage. Keep it secret — never commit it.)

The workflow (`.github/workflows/desk.yml`) then runs every 30 min, 04:00–11:30 UTC
Mon–Fri (~09:00–16:30 PKT). Trigger the first run manually: repo → Actions →
"PSX Desk cloud pipeline" → Run workflow.

## 3. Deploy the dashboard to Vercel
1. vercel.com → Add New → Project → import the GitHub repo.
2. **Root Directory: `dashboard`**  (important — this makes `index.html` the site root).
3. Framework preset: **Other**. No build command. Deploy.

That's it. Vercel serves the dashboard; it fetches JSON from the Supabase public bucket.
Every 30 min GitHub Actions refreshes the data and the dashboard picks it up.

## Populate the bucket right now (optional, from your PC)
To see live data before the first Actions run:
```powershell
cd "D:\PSX Trader X Claude"
$env:SUPABASE_URL="https://qteoncckohuoatbjjykb.supabase.co"
$env:SUPABASE_SERVICE_KEY="<your service_role key>"
python scripts\upload_supabase.py --deep
```

## Cost / free-tier notes
- **GitHub Actions**: public repo = unlimited minutes. Each run ~3–5 min.
- **Supabase free**: 1 GB storage, 5 GB egress/month, project pauses after 1 week idle —
  the 30-min cron keeps it awake. JSON-only bucket stays well under 1 GB.
- **Vercel Hobby**: free static hosting + CDN. (Vercel's own cron is daily-only and its
  functions time out at ~60 s — that's why the 30-min pipeline runs on GitHub Actions, not
  Vercel.)
- **Deep history** (19 y, the heavy fetch) is cached and only re-pulled once per day.

## Later, if you want the agents in the cloud too
Add `ANTHROPIC_API_KEY` as a secret and a second workflow that runs `claude -p` with the
pre-market prompt. That costs tokens (a few $/month at daily cadence) — deferred by choice.
