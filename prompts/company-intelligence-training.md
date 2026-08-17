# Company Intelligence synthesis training

Read CLAUDE.md and docs/OPERATIONS.md. This loop is manual and owner-gated.

1. Run the deterministic data pipeline first. Stop if preflight or document-intelligence checks fail.
2. Run `python scripts/prepare_synthesis_batch.py --limit 10`. It selects pending rows
   deterministically, balances companies, excludes approved receipts, and writes a compact ignored handoff.
3. For each item in that handoff, run `company-intelligence-librarian`. It writes only to ignored `.cache/`.
4. Run `company-intelligence-verifier` independently on each candidate.
5. Run `python scripts/company_brief_review.py validate <candidate>` for every candidate.
6. Present the clean candidates and verifier findings to the owner. Do not approve on the owner's behalf.
7. Only after explicit owner approval, run `python scripts/company_brief_review.py approve <candidate> --verification <candidate>.verification.json --owner-confirmed`.
8. Rebuild the CI slice, run preflight, and publish through the one documented path.

Never put a model key in GitHub Actions. Never run when the queue delta is zero. Keep rejected or blocked
candidate files in ignored cache for diagnosis; durable state receives only owner-approved briefs and receipts.
