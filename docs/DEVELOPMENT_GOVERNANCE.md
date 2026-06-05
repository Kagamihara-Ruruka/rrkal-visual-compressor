# Development Governance

This repository follows RRKAL-style development discipline: keep the core model
small, keep source truth separate from projections, and make every feature
testable through documented commands.

## Source Of Truth

- Raw input data is read-only.
- Compressed visual models are the source of reconstruction.
- SVG, demo scripts, PNGs, and editor views are exports, not the canonical data.
- Future `.vizasset` packages must keep source metadata, processing parameters,
  fidelity metrics, and lineage together.
- Renderer/runtime interoperability assumptions are tracked in scoped review artifacts
  until downstream owners confirm runtime ownership:
  - `docs/benchmarks/README.md`
  - `docs/benchmarks/CONTRACT.md`
  - `03_OAI_Review_Requests` in Notion.

## MVP Boundary

The current mainline is:

```text
time series -> compact visual model -> SVG/demo.py/metrics
```

Features belong on the mainline only if they improve this flow. Longer-term
ideas such as 2D shape fields, void/material assets, 3D implicit assets, Unreal
projection, or editor UI should stay in docs, contracts, or isolated stubs until
they have a CLI path and tests.

## Project Boundaries

- This repo owns compression algorithms, visual model contracts, metrics, and
  export preparation.
- The editor repo owns interaction, styling, annotation, and Photoshop-like UI.
- RRKAL owns asset registry, source manifests, install state, and broader data
  lineage.
- Runtime engines are consumers of exported packages, not owners of the model.

## Engineering Rules

- Primary development workspace is:
  `L:\rrkal-visual-compressor`.
- Session boot protocol follows `docs/AGENT_START_HERE.zh-TW.md` before each new
  major action slice:
  - confirm workspace / git state
  - read this repo's primary handoff and governance references
  - confirm Notion route health
  - define bounded slice and file boundaries
  - run pre-commit validation checks before checkpoint handoff.
- Primary coordination has moved to Notion: [Agents討論區](https://www.notion.so/Agents-37278539890480218eb3e5890d287bd8?t=3727853989048067971400a9e290a662);
  cloud-drive exchange is archive-only and not used as primary coordination.
  - `04_Agent_Inbox`: status / handoff / relay.
  - `03_OAI_Review_Requests`: `o_1` review requests.
  - `02_Decision_Log`: accepted decisions.
  - `06_n1_SOP`: `n_1` operations.
- `L:\AGENT_EXCHANGE` is retained as archive/history reference only.
- In this session, other folders on `L:` are treated as read-only unless explicitly
  permitted for the current task.
- GitHub must stay synchronized from this project workspace; after commits, push
  `main` to `origin`.
- Generated outputs are reviewed before commit, and one-off artifacts (including
  MVP/bench output folders) should be cleaned from the working tree unless they
  are officially tracked docs artifacts.
- Every new user-facing feature needs a CLI route, tests, and metrics output.
- Do not add hidden one-off scripts for core behavior.
- Do not commit generated outputs, private datasets, caches, or local runtime
  artifacts.
- Prefer small, typed modules over sample-code adoption.
- Update docs when a change affects usage, architecture, roadmap, or agent
  handoff.
- Treat compression claims as measurable hypotheses: report sample count,
  parameter count, error, and coverage instead of relying on theory alone.

## Research Gate

Before promoting a research idea into implementation, answer:

1. What MVP segment does it serve?
2. Which CLI command exercises it?
3. Which test proves it works?
4. Which metrics show whether it wins or loses?
5. If removed, would the current MVP break?

If the answer to the last question is "no", keep it behind a documented
research boundary until the mainline needs it.
