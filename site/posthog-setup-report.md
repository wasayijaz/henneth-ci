# PostHog post-wizard report

The wizard has completed a full PostHog integration for the Henneth PSX desk marketing site (Astro SSG). PostHog is initialised via the CDN snippet in a reusable `src/components/posthog.astro` component, injected into every page through `src/layouts/Base.astro`. The snippet uses `is:inline` to prevent Astro from processing it and to avoid TypeScript errors on `window.posthog`. Initialisation is gated behind `import.meta.env.PROD` to match the existing GA4 convention and avoid polluting analytics from dev/preview builds. Ten custom events are captured across six files, covering the full visitor journey from landing on the homepage through ticker research to plan signup intent.

| Event | Description | File |
|---|---|---|
| `hero_cta_clicked` | Visitor clicked "Get started" or "See the track record" in the hero section | `src/pages/index.astro` |
| `desk_room_demo_played` | Visitor clicked play on the homepage desk room debate animation | `src/pages/index.astro` |
| `plan_started` | Visitor clicked a plan tier's CTA button on the plans page | `src/pages/plans.astro` |
| `faq_expanded` | Visitor expanded an FAQ item on the plans page | `src/pages/plans.astro` |
| `billing_period_switched` | Visitor toggled between monthly and annual billing (priced plans) | `src/components/PlansPaid.astro` |
| `ticker_viewed` | Visitor landed on a PSX ticker research page (includes `ticker_symbol`, `sector`) | `src/pages/psx/[ticker].astro` |
| `contact_link_clicked` | Visitor clicked a contact channel link (includes `contact_type`) | `src/pages/contact.astro` |
| `tool_calculated` | Visitor ran a calculation in a financial calculator (includes `tool_name`) | `src/scripts/calculators.ts` |
| `nav_cta_clicked` | Visitor clicked "Get started" or "Sign in" in the global nav bar | `src/components/Header.astro` |
| `mobile_nav_opened` | Visitor opened the mobile navigation drawer | `src/components/Header.astro` |

## Next steps

Five insights and a dashboard have been created in PostHog to monitor user behaviour from day one:

- [Dashboard — Analytics basics (wizard)](https://us.posthog.com/project/522643/dashboard/1884361)
- [Plan started by plan (wizard)](https://us.posthog.com/project/522643/insights/9QPoCsk4) — bar chart of plan_started broken down by plan_name
- [Conversion funnel: hero CTA → plan started (wizard)](https://us.posthog.com/project/522643/insights/pfAGF78r) — 7-day ordered funnel
- [Ticker pages viewed by sector (wizard)](https://us.posthog.com/project/522643/insights/CdJYTbRD) — stacked bar of ticker_viewed by sector
- [Desk room demo plays (wizard)](https://us.posthog.com/project/522643/insights/38uq4GtK) — daily line of demo engagement
- [Tool calculations by tool (wizard)](https://us.posthog.com/project/522643/insights/eCfvbjrM) — weekly bar of tool_calculated by tool_name

## Verify before merging

- [ ] Run a full production build (`npm run build`) and fix any lint or type errors introduced by the generated code.
- [ ] Run the test suite — call sites that were rewritten or instrumented may need updated mocks or fixtures.
- [ ] Add `PUBLIC_POSTHOG_PROJECT_TOKEN` and `PUBLIC_POSTHOG_HOST` to `.env.example` and any onboarding docs so collaborators know what to set.
- [ ] Wire source-map upload (`posthog-cli sourcemap` or your bundler's upload step) into CI so production stack traces de-minify in PostHog error tracking.

### Agent skill

We've left an agent skill folder in your project at `.claude/skills/integration-astro-static/`. You can use this context for further agent development when using Claude Code. This will help ensure the model provides the most up-to-date approaches for integrating PostHog.
