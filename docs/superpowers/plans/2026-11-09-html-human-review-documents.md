# HTML human review documents implementation plan

**Goal:** Make project specs, brainstorms, plans and reviews pleasant to consume as offline HTML, with the most important review items first.

**Base:** `origin/master` at `2c18603`; independent of the CFR-GLM/framework PRs.

**Architecture:** Keep Markdown as an authoring/machine-readable source. A reusable optional documentation package builds deterministic adjacent HTML files and a review catalogue. Agent policy and check-only hooks require future human-facing documents to have current HTML counterparts.

## Discovery and design decisions

- The authoritative baseline has 27 tracked Markdown sources, including 25 human-facing documents plus agent policy/history. Local `master` is stale; use `origin/master`.
- Current documents use tables, nested lists, code fences, links, checkboxes and long historical plans. Parse Markdown tokens; never infer headings from lines inside code fences.
- Use pinned `markdown-it-py==4.0.0` in optional `docs` and existing `dev` extras, keeping Python game dependencies empty. Reuse its [documented token and renderer API](https://markdown-it-py.readthedocs.io/en/latest/using.html). Synchronize new dependency declarations in pyproject.toml/setup.py.
- Pages contain hierarchical section navigation, a document map, readable tables/code and source identities. Active reviews additionally expose a priority queue and local reading-progress controls.
- Priorities are explicit heading prefixes: `Blocker:`, `Important:`, `Decision:`, `Nit:`, `Pre-existing:`. Only documents explicitly marked active review contribute active findings. Historical unchecked tasks remain source status, not current blockers.
- Metadata is an optional first-line comment: `<!-- human-review: {"kind":"review","status":"active"} -->`. Missing metadata defaults to reference status. No inference from old unresolved prose.
- SVG is the portable diagram format. Inline safe local SVG images in HTML; provide workflow/priority diagrams and authoring templates. No CDN/online rendering or Node dependency. Mermaid authors export SVG before linking it.
- Markdown remains canonical; generated HTML is tracked and deterministic. The catalogue defaults to public Git-visible Markdown, excluding private/hidden agent directories and ignored training runs. Explicit single-file rendering supports ignored run summaries.
- Existing training algorithms/writers remain unchanged. Agents render their Markdown outputs to HTML before delivery; future native HTML producers can keep their existing data interfaces.

## Task 1: safe token-based rendering

- [x] Add failing tests for heading hierarchy excluding fenced code comments, tables/task lists, duplicate anchors, safe markup/links, embedded SVG and image containment.
- [x] Create `src/mus_computer/documentation/` with reusable rendering and CLI APIs. Keep parser import optional and show an actionable install error.
- [x] Add explicit active-review metadata, priority ordering, source-status badges, a section map and reading-progress controls; preserve source text/status.
- [x] Verify no external assets, executable source HTML or automatic network requests enter generated pages.

## Task 2: build/index and ongoing enforcement

- [x] Add tests for deterministic builds/check mode, public document discovery, private/ignored directory exclusion, relative Markdown link rewriting and stale/missing HTML detection.
- [x] Implement `python -m mus_computer.documentation build`, `check`, and `render SOURCE.md`, with adjacent HTML and a catalogue at `docs/review/index.html`.
- [x] Add `make docs`/`docs-check`, a check-only pre-commit documentation gate and CI freshness check. Generated output must never modify training snapshots.
- [x] Update only new optional dependencies in both packaging declarations. CI's existing dev installation supplies the parser.

## Task 3: project guidance and existing documents

- [x] Add HTML-first authoring/review guidance to root AGENTS.md, preserving existing review rules and single repair allowance. Require meaningful diagrams, hierarchical sections and explicit priorities for future reviews.
- [x] Add review/spec/brainstorm templates, an active review document for this PR, and offline SVG workflow/priority diagrams.
- [x] Build HTML counterparts for existing public documents; keep historical metadata intact. Add a root README link to the catalogue.
- [x] Visually verify a real review page and historical spec/plan on desktop and a narrow viewport; exercise visible reading controls.

## Task 4: checks and PR

- [x] Run tests plus configured lint/format/type/secret hooks and HTML freshness checks. Scan intended new sources and generated HTML before independent review.
- [x] Perform one independent review, at most one verified Important repair batch, then a read-only repair-delta review.
- [ ] Verify exact staged revision, commit/push this dedicated branch and open a separate PR against master. Verify CI/review and report any remaining blockers without merging automatically.

## Boundaries

- Do not import the unmerged experiment framework or alter bot training/game logic.
- Do not rewrite globally installed skills. Project guidance and templates apply within this repository.
- Do not discover/publish unrelated `.claude`, `.codex`, `.agents`, virtual environments, ignored runs or arbitrary external files.
- Reading checkmarks are local review progress, not approvals, verified fixes or Git merges.
