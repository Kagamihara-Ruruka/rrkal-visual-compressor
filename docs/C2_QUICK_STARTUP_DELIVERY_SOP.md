# C2 Quick Startup + Delivery SOP (Docs/Readiness Lane)

Scope: c_2 docs/evidence/startup/handoff/taxonomy/encoding.

## 1) Scope lock (one coherent slice only)

Before edits, declare the slice boundary in one sentence:

- theme: `docs-readiness` OR `encoding-cleanup` OR `startup-doc hygiene` OR `evidence taxonomy`.
- no mixing with feature work, algorithm/manifest changes, or cross-repo integration work.

Allowed deliverables:
- startup docs
- handoff docs
- taxonomy/evidence docs
- encoding-readability remediation

Forbidden within this lane:
- .vizasset manifest/schema changes
- CLI behavior changes
- compression algorithm changes
- downstream-ready claims (no `ready for adoption`, `production-ready`, `directly consumable`, etc.)
- cross-repo implementation

## 2) Preflight (must-run in every slice)

Run in repo root `L:\rrkal-visual-compressor`:

- `git status --short --branch`
- `git log -1 --oneline --decorate`
- read required governance/doc files before edits
- confirm Notion route for coordination

Required reads:

- `docs/AGENT_START_HERE.zh-TW.md` (startup policy)
- `docs/AGENT_HANDOFF.md` (handoff context)
- `docs/DEVELOPMENT_GOVERNANCE.md` (repo boundary and governance)
- `docs/ROADMAP.md` / `docs/ROADMAP.zh-TW.md` (release context)

If any required file is unreadable/absent, stop and escalate as documentation debt.

## 3) Execution rule

- One slice => one theme.
- One lane run should not fix more than one design direction.
- Keep change intent in one paragraph inside docs (or one section in one document).
- No generated artifacts in scope; keep scratch outputs ignored, not committed.

## 4) Validation tiers

### Tier 0 (must-run for all lane runs)

- `git diff --check` (line ending / whitespace sanity)
- "RRKAL doc readability guard" checks (see section 5)
- repo clean-state checks before/after required by report (or staged delta expected)
- avoid changing command behavior; if docs only, keep behavior tests skipped unless command docs are altered.

### Tier 1 (must-run only if CLI behavior docs changed)

- `python -m vizcompress --help`
- `python -m vizcompress.cli --help`
- relevant docs/README consistency checks for command signature text changes
- `python scripts/docs_readability_checkpoint.py` (docs readability checkpoint bundle)

### Tier 2 (docs-only, optional/skip-if-doc-only)

- `python -m pytest -q` (skip if only text edits)
- focused docs-linked smoke/check commands if handoff explicitly ties to functionally validated behavior.

### Tier 3 (must-run if docs mention startup/test evidence)

- spot-check evidence command text consistency against latest validated outcomes in handoff
- ensure no unsupported commands are introduced as mandatory evidence

## 5) RRKAL doc readability guard (mandatory for docs slices)

For every touched `.md` / `.zh-TW` file:

1. UTF-8 strict decode check
2. U+FFFD scan (`U+FFFD` presence) to detect decode artifacts
3. Encoding drift check for known startup docs and new/edited startup references
4. PUA / mojibake marker scan via repo-local script:
   - `python scripts/check_docs_readability.py scripts/check_docs_readability.py docs/AGENT_START_HERE.zh-TW.md docs/AGENT_HANDOFF.md docs/C2_QUICK_STARTUP_DELIVERY_SOP.md` (`non-warning baseline`)
   - `python scripts/check_docs_readability.py --strict tests/fixtures/docs_readability/contains_fffd.md tests/fixtures/docs_readability/contains_pua.md` (`fixture guard: expects warning for negative fixtures`)
5. Required-token presence check for startup docs:
   - `git status --short --branch`
   - `git log -1 --oneline --decorate`
   - Notion spaces (`04_Agent_Inbox`, `03_OAI_Review_Requests`, `02_Decision_Log`, `06_n1_SOP`)
6. If new missing-doc references are found, downgrade them (e.g., "if exists", "if available") rather than hard-require unknown files.

## 6) Delivery output format (required handoff artifact)

Before requesting review or close, include:

- Repo
- Branch
- HEAD
- Files changed
- Validation run list + pass/fail
- evidence status (what changed, what still pending)
- warning/status for startup consistency
- stop conditions encountered
- boundary statement
- final git status
- classification line

Template:

```text
Repo:
Branch:
HEAD:
Scope:
Files changed:
Validation:
Startup consistency:
Boundary statement:
Stop conditions:
Final classification:
```

## 7) Stop conditions for this SOP lane

- UTF-8 decode or U+FFFD failure in edited docs
- any edit requires CLI/schema/runtime behavior to be changed
- missing referenced startup files that cannot be safely corrected locally
- accidental drift into `renderer/runtime integration` or `cross-repo implementation`

## 8) Boundary statement (copy into lane report)

- no manifest/schema change
- no CLI behavior change
- no compression algorithm change
- no integration-ready claim
- no RRKAL Core / Display / Odoriba schema alignment claim

## 9) Notes for c_2

- This SOP is for documentation-readiness and encoding hygiene.
- Code changes in this lane require o_1 review reclassification before scope extension.
- Evidence-first wording is preferred over certainty-first wording:
  - prefer `planning input` over `directly consumable`
  - prefer `supported for review` over `officially adopted`

## 10) Negative fixtures for readability checker (docs-readability lane)

Use `tests/fixtures/docs_readability/` for reproducible negative cases:

- `clean.md` (PASS)
- `contains_fffd.md` (warning with `U+FFFD` marker)
- `contains_pua.md` (warning with PUA marker)

Local execution:

- `python -m pytest tests/test_docs_readability_checker.py -q`
- `python scripts/check_docs_readability.py --strict tests/fixtures/docs_readability/contains_fffd.md tests/fixtures/docs_readability/contains_pua.md`

## 11) Checkpoint bundle (required for docs-touching lane close)

- `python scripts/docs_readability_checkpoint.py`

Expected checkpoint report flags:

- `clean_docs_scan_passed=true` (`true` if docs scan returns no UTF-8/marker risk)
- `negative_fixture_detection_passed=true` (`true` if fixtures detect the expected warnings in strict mode)
- `cli_help_passed=true` (`true` if both CLI help commands render)
- `no_manifest_schema_change=true` (`true` if no manifest/schema scoped paths changed)
- `readability_pytest_passed=true` (`true` if `tests/test_docs_readability_checker.py` passes)
- `checkpoint_passed=true` (`true` if all required checks pass)
- `schema` (schema tag, e.g. `docs-readability-checkpoint/v1`)
- `status` (`pass` | `fail`)
- `boundary` (docs-only checkpoint boundary object)

JSON mode:

- `python scripts/docs_readability_checkpoint.py --json`
- JSON output includes all required keys above with `boundary` and `status`.
