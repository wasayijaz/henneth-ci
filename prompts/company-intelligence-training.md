# Company Intelligence synthesis training

Read AGENTS.md, README.md and docs/OPERATIONS.md. This loop is manual and owner-gated.
Use Luna High for the librarian and an independent Luna High verifier task.

1. Follow docs/CI_REFRESH.md for the manual CI-only refresh. Stop if any refresh, preflight or document-intelligence check fails. Never run the Desk pipeline from here.
2. Run `python scripts/prepare_synthesis_batch.py --limit 10`. It selects pending rows
   deterministically, balances companies, excludes approved receipts, and writes a compact ignored handoff.
3. For each item in that handoff, run `company-intelligence-librarian`. It writes only to ignored `.cache/`.
4. Run `company-intelligence-verifier` independently on each candidate.
5. Run `python scripts/company_brief_review.py validate <candidate>` for every candidate.
6. Present the clean candidates and verifier findings to the owner. Do not approve on the owner's behalf.
7. Only after explicit owner approval, run `python scripts/company_brief_review.py approve <candidate> --verification <candidate>.verification.json --owner-confirmed`.
8. Rebuild the CI slice and integrity artifacts, run the product-contract aggregate and preflight, then use the controlled CI release workflow documented in docs/OPERATIONS.md. Never use Desk publish.py or bypass authenticated preview checks.

Never put a model key in GitHub Actions. Never run when the queue delta is zero. Keep rejected or blocked
candidate files in ignored cache for diagnosis; durable state receives only owner-approved briefs and receipts.
