**Source visual truth**

- Path: `E:\Chrome Downloads\pencil-export.html`
- Intended viewport: 1920 × 1080 desktop terminal
- State: Company Intelligence, MLCF selected, directory tree visible

**Implementation evidence**

- Intended local URL: `http://127.0.0.1:4173/`
- Implementation screenshot: unavailable
- Viewport, source/implementation pixel dimensions, CSS size, and density normalization: unavailable because the in-app browser runtime could not initialise on this host (`failed to write kernel assets: path not found`).
- Full-view and focused-region visual comparison: unavailable; visual fidelity cannot be assessed from source code alone.
- Primary interactions independently exercised by deterministic checks: company navigation, Company Brain, Ask Henneth, and CI monitoring UI contracts. Console inspection: unavailable without a browser-rendered session.

**Findings**

- [P1] Visual comparison is blocked
  Location: entire dashboard shell.
  Evidence: the selected Pencil export and a browser-rendered dashboard screenshot could not be opened together in the required browser surface.
  Impact: the four-pane layout, frosted surfaces, responsive collapse, type scale, and folder-tree interaction cannot be truthfully signed off as visually matching the source.
  Fix: restore the in-app browser runtime, capture the source and `http://127.0.0.1:4173/` at 1920 × 1080 plus narrow breakpoints, then run the specified side-by-side review.

**Open Questions**

- The reference uses icon artwork; the implementation uses readable rail labels to avoid substituting decorative Unicode pseudo-icons. A visual pass should decide whether approved real icon assets are needed for closer fidelity.

**Implementation Checklist**

- [x] Preserve the authenticated data and company-navigation contracts.
- [x] Implement the four-pane desktop structure and the six requested directory groups.
- [x] Run syntax and focused UI contract checks.
- [ ] Capture and compare the rendered desktop and narrow layouts against the Pencil export.

**Follow-up Polish**

- After a browser capture is available, tune icon treatment, exact frosted opacity, spacing, and type density against the visual reference.

final result: blocked
