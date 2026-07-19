# Deploying Henneth AI

Hosting is **Vercel**, serving a static site straight from this repo. There is no server,
no GitHub Actions, and no Supabase Storage bucket in the data path.

```
Local refresh loops (Claude app)  ──git push main──▶  GitHub (private repo)
                                                          │  push auto-triggers
                                                          ▼
                                              Vercel  ──builds + serves──▶  live site
```

`vercel.json` assembles the site on each deploy: it copies `dashboard/index.html`,
`app.js`, `themes.css` and the committed `state/` data into `public/`. The dashboard
fetches `state/*.json` as static files from Vercel (`DATA_BASE = "state/"`), so a `git push`
to `main` is the entire deploy — Vercel rebuilds in ~30–60 s.

## Pushing an update
Never `git push` by hand for a data refresh — use the gated helper, which runs `preflight.py`
first and only commits/pushes if state actually changed:
```powershell
cd "D:\PSX Trader X Claude"
python scripts\publish.py "Your message"
```
If preflight fails (the data would render broken), it aborts and nothing publishes.

## Accounts (Supabase)
Supabase is used **only for auth + per-user data** (profiles, watchlist), never for serving
the research data. Project `qteoncckohuoatbjjykb`. The client uses the *publishable* key
(safe to ship); Row-Level Security enforces that each user can read/write only their own row.
The `service_role` (secret) key must never be committed and is not needed by the site.

## Free-tier notes
- **Vercel Hobby**: static hosting + CDN, 100 GB bandwidth/month (~low-thousands of active
  users before you'd consider Pro).
- **Supabase free**: 50k monthly active users, 500 MB DB — plenty for auth + profiles.

## Later, if you want cloud-run agents
The agents run locally today (token cost stays on your machine, and the loops push results).
To move them to the cloud, add `ANTHROPIC_API_KEY` as a secret and a runner that executes
`claude -p` with the pre-market prompt — deferred by choice (a few $/month at daily cadence).
