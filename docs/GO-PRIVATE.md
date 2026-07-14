# Go private: move hosting to Vercel, then make the repo private

Goal: the source is **not public**, the live product keeps working and auto-updating.
GitHub Pages (free) requires a public repo, so hosting moves to **Vercel** first, then we flip the repo private.

The repo is already prepared: chart data is committed and `vercel.json` builds the static site.

---

## Step 1 — Connect the repo to Vercel (your account; ~3 clicks)

1. Go to **vercel.com** → sign in with GitHub (`wasayijaz`).
2. **Add New… → Project** → **Import** `wasayijaz/psx-trade-desk`.
3. Vercel reads `vercel.json` automatically — **Framework: Other**, build + output are pre-set. Just click **Deploy**.
4. Wait ~1–2 min → you get a URL like `psx-trade-desk.vercel.app`. Open it — the whole desk should load (board, tickers, charts, accounts).

That's it — from now on **every push auto-deploys** (the refresh tasks push fresh data → Vercel rebuilds).

## Step 2 — Point accounts at the new domain

Supabase Dashboard → **Authentication → URL Configuration**:
- **Site URL** = your Vercel URL (e.g. `https://psx-trade-desk.vercel.app/`)
- Keep `http://localhost:8877/dashboard/` in **Redirect URLs** for local dev.

(No code change — the Supabase publishable key already works from any origin.)

## Step 3 — Tell me it's live, and I flip the repo private

Once you confirm the Vercel URL works, I run:
```
gh repo edit wasayijaz/psx-trade-desk --visibility private
```
and the source is no longer public. Vercel keeps serving (Hobby supports private repos); the scheduled
refresh tasks keep pushing → Vercel keeps redeploying.

---

## What changes vs today (know this before flipping)

- **Hosting:** GitHub Pages → Vercel. The `wasayijaz.github.io/psx-trade-desk` URL stops once private; the
  `.vercel.app` URL (or a custom domain you add in Vercel) is the new home.
- **Data refresh:** the **local scheduled tasks** (which `git push`) drive updates → Vercel redeploys.
  The old **GitHub Actions 30-min cron deployed to Pages** — on a private repo that Pages deploy no longer
  applies. Two clean options for the cloud/app-independent refresh:
  1. Leave the Actions workflow disabled (the local tasks handle refresh while the app is open). Simplest.
  2. Later: add a **Vercel Deploy Hook** and have the Actions pipeline curl it after building — restores a
     truly app-independent 30-min refresh. (One workflow edit; you'd paste it since the token can't push workflows.)
- **Actions minutes:** private repos get 2000 free min/month. The current cron is near that ceiling, so
  option (1) above (rely on local tasks, or trim the cron cadence) keeps you inside free.
- **Custom domain:** add one in Vercel (Project → Domains) for a branded product URL later.

## Rollback
If anything's off, the repo can go public again instantly (`--visibility public`) and Pages resumes — nothing is lost.
