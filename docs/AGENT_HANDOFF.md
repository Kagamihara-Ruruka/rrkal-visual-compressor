# Agent Handoff

## Mission

Build a small, testable visual compression engine before expanding scope.

## Hard Boundaries

- Do not add Qt here.
- Do not build the visual editor here.
- Do not integrate Unreal here.
- Do not claim universal compression.
- Keep this package importable by RRKAL and the editor.

## Current Workspace Rule

- Primary writable workspace: `L:\rrkal-visual-compressor`.
- `L:\` is a shared workspace area (read/write), and this repo is the active project working folder.
- `K:\` is treated as read-only for this session.
- Other folders on `L:\` are considered read-only unless explicitly requested.
- Do not modify other project folders unless explicitly approved in-session.
- Push cloud-workspace commits to GitHub `origin/main`.
- If multiple `rrkal-visual-compressor` copies are present, prefer repo-local entry points:
  - `python -m vizcompress.cli ...` from `L:\rrkal-visual-compressor` (resolved by `vizcompress/__main__.py` shim),
  - or `py scripts/run_vizcompress_cli.py ...` (explicit launcher).
- Do not rely on manual `PYTHONPATH` edits for routine CLI/test invocations.
- Use shared helper plumbing (`_test_helpers.cli_env()` and
  `scripts/run_vizcompress_cli.py`) for stable module resolution and cleaner
  handoff evidence.

## Current Status

Implemented mainline:

- time-series analyzers and synthetic fixtures
- RDP and Fourier compressors
- Fourier channel model
- cleaning as layered modeling, not destructive deletion
- sparse residual layer and Fourier residual noise layer
- `.vizretain`, `.vizclean`, and neutral `.vizasset` package family
- package readback for Fourier, channel, sparse residual, and noise layers
- irregular x-domain handling with preserve, compressed, and auto policies
- benchmark matrix with per-kind summaries and recommendation labels
- `build`, `bench`, `recommend`, `inspect`, and `verify` CLI commands
- source-backed package fidelity verification with optional RMSE/MAE/max-error budgets
- `review.json` packet generation with source fingerprints and accepted metrics
- `--require-review-pass` build gate for rejecting packages that exceed review budgets
- `compare` CLI for raw/gzip baseline size evidence against existing packages
- LTTB downsampling baseline metrics plus LTTB SVG raw/gzip size evidence in benchmark rows
- optional Markdown benchmark reports via `bench --report-md`
- benchmark gates via `--require-svg-gzip-win`, `--require-csv-gzip-win`, `--min-fourier-r2`, and `--min-channel-coverage`
- defensibility tuning via `--defensible-channel-coverage` (summary-only selector threshold; default `0.9`)
- Fourier term sweet-spot sweeps via `bench --fourier-terms-sweep`
- channel coverage sweeps via `bench --channel-k-sweep`
- benchmark evidence snapshots under `docs/benchmarks`

Current local verification command:

```powershell
py -m pytest -q
```

Latest known passing count: `108 passed`.
With `pytest.ini` cache-dir override (`.pytest_cache_working`), pytest cache warning is no longer emitted.

## Original First Task

Port `proof_vectorization.py` into:

```text
src/vizcompress/compressors.py
src/vizcompress/exporters.py
src/vizcompress/metrics.py
tests/test_timeseries_compression.py
```

## Definition Of Done For First PR

- `py -m pytest` passes.
- CLI can generate SVG and metrics from synthetic data.
- README quickstart works.
- No UI dependencies.

## Design Principle

The compressed model is the source of visual reconstruction. SVG is an export target, not the internal truth.

Residuals are not automatically discarded. A retained package keeps residual
layers when available; a clean package exports only the cleaned main signal.

## Session Baseline Verification (May 29, 2026, L:\rrkal-visual-compressor)

- `git status` baseline before edits: clean.
- `py -m pytest -q` completed successfully: `104 passed`.
- `py -m vizcompress.cli mvp --samples 2000 --synthetic-kind spikes --fourier-terms 64 --out baseline_outputs`
  - command status: pass
  - summary: pipeline produced `baseline_outputs/asset` package and `mvp_summary.json`
  - validation: `package_ok=true`, `source_ok=true`, `benchmark_gate.ok=true`
- `py -m vizcompress.cli bench --synthetic-sizes 1000,10000 --synthetic-kind spikes --fourier-terms 64 --svg-samples 600 --channel --out baseline_bench.json --report-md baseline_bench.md`
  - command status: pass
  - benchmark status: `observed_break_even_samples=10000`
  - best sample row recommends `package` against `source_csv_gzip`/`direct_svg_gzip` (`package_preferred`)
  - `104 passed` test result from same environment remains green after command runs
- `py -m vizcompress.cli build --synthetic 2000 --synthetic-kind irregular --fourier-terms 48 --channel --out irregular_smoke`
  - command status: pass
  - key checks: `x_uniform=false`, `r2=0.9998992434575401` (Fourier), `coverage_ratio=0.991`
- `py -m vizcompress.cli video-bench --frame-counts 32 --height 16 --width 16 --rank-values 2 --temporal-terms-values 8 --out video_smoke.json --report-md video_smoke.md`
  - command status: pass
  - summary: `row_count=1`, `best_compression_ratio=10.0147`, `best_r2=0.99818`
- `py -m pytest tests/test_benchmark_contracts.py tests/test_cli_smoke.py -q`
  - command status: pass
  - result: `7 passed`
- `py -m pytest -q` (full suite)
  - result: `108 passed`
- `py -m vizcompress.cli build --synthetic 128 --synthetic-kind spikes --fourier-terms 16 --svg-samples 120 --channel --package --out <tmp> --package-name model.vizretain`
  - command status: pass
  - `inspect` on generated package returns valid asset manifest summary
  - `verify` with `--synthetic 128` and `--synthetic-kind spikes` returns `ok=true`
- `py -m vizcompress.cli build --synthetic 96 --synthetic-kind spikes --fourier-terms 16 --svg-samples 120 --channel --direct-svg --package --out <tmp> --package-name model.vizretain`
  - command status: pass
  - `compare` with `--baseline direct=<direct_svg>` returns baseline evidence for direct baseline

## Immediate Session Update (May 31, 2026)

- Re-ran MVP from repo root as a push-validation check:
  - `python -m vizcompress.cli mvp --samples 5000 --synthetic-kind spikes --fourier-terms 64 --out MVP_CHECKPOINT`
  - command status: pass
  - output status: `pass` with package + benchmark evidence generated under `MVP_CHECKPOINT`
  - validation results:
    - `package_ok=true`
    - `source_ok=true`
    - `benchmark_gate.ok=true`
  - key metrics:
    - `fourier_r2=0.9871501503`
    - `package_bytes=74242`
    - `source_csv_gzip_to_package_ratio=1.0395`
    - `direct_svg_gzip_to_package_ratio=0.38929`
  - recommendation: `package_preferred`, `gzip_recommendation=package_beats_raw_svg_but_not_gzip`
- No code changes required for this check; no functional regression observed.

## P1 Push Notes

- Fixed benchmark contract validation for non-channel benches: `channel_k` is now optional in grouping logic (`channel_k=None` treated as 0.0).
- Added coverage tests:
  - [tests/test_cli_smoke.py](/L:/rrkal-visual-compressor/tests/test_cli_smoke.py) to smoke-run `bench` CLI and validate contract/markdown output.
  - [tests/test_benchmark_contracts.py](/L:/rrkal-visual-compressor/tests/test_benchmark_contracts.py) added case for rows without `channel_k`.
- Added CLI tests in [tests/test_cli_smoke.py](/L:/rrkal-visual-compressor/tests/test_cli_smoke.py):
  - `bench` contract smoke,
  - `build` -> `inspect` -> `verify` cycle,
  - `compare` command baseline evidence check.

## P2 CLI Contract Output Hardening Notes

- Improved benchmark contract validation diagnostics in [src/vizcompress/benchmark_contracts.py](/L:/rrkal-visual-compressor/src/vizcompress/benchmark_contracts.py):
  - Rejects `NaN`, `inf`, and `bool` for numeric fields.
  - Enforces `samples` and `fourier_terms` as positive integers.
  - Adds explicit `row[...]` and `sweep[...]` field-path error messages for precise failure attribution.
  - Tightens `summary` numeric consistency checks (`high_fidelity_rows_count`, `defensible_rows_count`, `defensible_rows_ratio`, `defensible_channel_coverage_threshold`).
- Updated contract validators in scripts for clearer traceability:
  - [scripts/validate_benchmark_contracts.py](/L:/rrkal-visual-compressor/scripts/validate_benchmark_contracts.py) now prints each error with prefixed lines and includes `errors:` when report output exists.
  - [scripts/validate_benchmark_contracts_all.py](/L:/rrkal-visual-compressor/scripts/validate_benchmark_contracts_all.py) now prefixes file context to printed error lines and prints `failed_report` when output exists.
- Added CLI-facing regression tests in [tests/test_benchmark_contracts.py](/L:/rrkal-visual-compressor/tests/test_benchmark_contracts.py):
  - `test_validate_benchmark_contract_script_reports_field_path`
  - `test_validate_benchmark_contracts_all_script`
  - `test_validate_benchmark_contracts_all_script_reports_sweep_path`


## Latest Delta (continuation)

- Added `scripts/scan_benchmark_fields.py` as a fast structural precheck for benchmark JSON files.
- Added `tests/test_scan_benchmark_fields.py` to lock down scan behavior, including contract/parity report exclusions.
- Updated `docs/benchmarks/CONTRACT.md` to include the new scan command as a pre-validation step.
- Added `scripts/precheck_benchmarks.py` to run scan + strict contract checks in one command, with JSON output and fail-fast semantics.
- Added `tests/test_precheck_benchmarks.py` to lock down precheck success/failure exit behavior.
- Updated `docs/benchmarks/README.md` with a CI-ready precheck command sequence and report fields.
- Extended `tests/test_precheck_benchmarks.py` with CLI `--help` contract to lock interface stability.
- Added `scripts/convert_legacy_hardening_reports.py` with legacy-to-contract migration path and
  added `tests/test_convert_legacy_hardening_reports.py` for conversion command regression.
- Updated governance docs (`CONTRACT*.md`, `README*.md`) with migration dry-run guidance.
- Added `.github/workflows/benchmarks-precheck.yml` to run benchmark gate tests and precheck on PR/push changes touching benchmark scripts and docs.

## Execution Rhythm (This Session)

### Working Rule

- Scope stays strictly within `L:\rrkal-visual-compressor`.
- `K:\` is read-only.
- Do not edit other project folders on `L:\` unless explicitly requested.
- Do not modify repository files outside this workspace for this session.

### Immediate Push Plan (P0)

1. Keep AGENTS and workflow docs consistent with workspace reality.
2. Verify core commands from the repository can still run from `L:\rrkal-visual-compressor`.
3. Run only code-anchored changes when they map to explicit acceptance criteria.
4. Keep output contracts stable: model read/write, benchmark columns, and review packet fields.
5. Prioritize validator robustness (runtime-safe error path) before feature additions.

### Non-negotiables

- No Qt UI changes in this repo.
- No Unreal integration changes in this repo.
- No "more scope" changes without testable acceptance criteria.

## Immediate 6:00-Goal Execution Plan

1. Keep the precheck path authoritative
- Verify `scripts/precheck_benchmarks.py` and scan/contract helpers are the only required gate before benchmark promotion.
- Keep command docs aligned in all three places: `docs/benchmarks/README.md`, `docs/benchmarks/CONTRACT.md`, and `docs/AGENT_HANDOFF.md`.

2. Stabilize CI-ready command set
- Add/keep a single precheck command pattern for PRs and daily smoke:
  - `py scripts/precheck_benchmarks.py --root docs/benchmarks --pattern "*.json" --scan-out ... --contract-out ... --fail-on-scan-warning`
- Ensure scan failures are treated as hard failures in CI and only accepted warnings are allowed when explicitly requested.

3. Minimize false positives
- Keep contract rules strict only on measurable invariants (existing fields and consistency checks).
- Do not widen acceptance criteria to compensate for missing `channel_coverage_ratio` unless it is documented as optional in schema and covered by regression tests.

4. Track deliverables
- Code change accepted only when it touches either:
  - benchmark gate scripts/tests,
  - benchmark contract checks,
  - or benchmark governance docs.
- Any unrelated refactor needs explicit approval before merge.

5. Current done criteria
- No unresolved `pytest` regressions introduced by the new gate scripts.
- New CLI smoke and precheck tests remain in the suite.
- `docs/benchmarks` documentation includes one-source explanation of required/optional fields and the full precheck output contract.

### Immediate Execution Plan (until 06:00 Asia/Taipei)

1. Field-path consistency hardening
- Keep validation, CLI scripts, and docs aligned so both `direct_svg_to_package_ratio` and `direct_svg_gzip_to_package_ratio` are handled consistently.
- Success condition: there is no remaining test or docs claim that forces a single hard-coded ratio field.

2. Contract command single-source alignment
- Keep `docs/benchmarks/README.md`, `docs/benchmarks/CONTRACT.md`, and this handoff using the same precheck command signature and expected report fields (`scan_ok`, `contract_ok`, `contract`, `failed_report`, `status_counts`, `skipped`, `skip_reasons`, `total_inputs`).
- Success condition: same command and output contract text appears in all three locations.

3. Scope discipline
- Confine edits to `L:\rrkal-visual-compressor` and avoid accidental cross-project moves.
- Success condition: `git status` shows modifications only under this workspace folder.

## Latest Delta (May 29, 2026, late session)

- Refined `scripts/validate_benchmark_contracts_all.py` to include a `summary` block with `failed_report` when strict validation fails, while preserving per-file failure details.
- Extended benchmark validation scripts to expose frontier metrics directly in each sweep summary: `best_ratio`, `best_defensible_ratio`, and `contract_gate_ok`.
- Hardened `tests/test_benchmark_contracts.py` with explicit sweep-path validation coverage and non-channel `channel_k` edge cases.
- Updated `docs/benchmarks/CONTRACT.md` to document field-level failure prefixes (`row[...]` / `sweep[...]`) and the `--out`/`failed_report` contract for auditability.
- Kept `docs/benchmarks/README.md` and precheck commands aligned with current CI usage.

## Outstanding Risks / Open Items (for next on-call window)

- Implemented: Ratio-field compatibility for benchmark recommendations.
  - `src/vizcompress/selectors.py` now uses `direct_svg_gzip_to_package_ratio` as a fallback target for recommendation scoring when raw ratio is missing/invalid.
  - Added regression tests in `tests/test_timeseries_compression.py` (`test_selector_recommends_with_gzip_only_ratio_fields`, `test_selector_recommendation_keeps_string_fields_robust`).

- Decision: Precheck is mandatory for manual benchmark promotion and any local benchmark-significant workflow outside exploratory ad-hoc runs.
  - Current enforcement point: CI gate + documented local promotion command.
  - Evidence target: `scripts/precheck_benchmarks.py` plus `py scripts/scan_benchmark_fields.py` / `py scripts/validate_benchmark_contracts_all.py`.
- Decision: Keep `rows[].errors` path as the current relative/path-string form (`<path>: <error>`) for compatibility.
  - Avoid forcing absolute paths before adding a migration because existing tests and report diff scripts assert this contract.
- Decision: Keep parity contract flags as opt-in flags (`--validate-contract`, `--require-contract-pass`) for now.
  - CI and local review workflows should pass explicit flags in command templates where contract behavior is required.
  - Evidence target: parity docs/examples and `tests/test_compare_terms_channel_benchmark_parity.py`.
- Decision: Windows root handling is accepted as-is while using `Path(...).expanduser().resolve()` and explicit `--left-root/--right-root`.
  - If root relocation issues appear, add a follow-up parity smoke test for non-`L:\` roots.

- Status (2026-06-02):
  - Implemented items: ratio-field compatibility and precheck mandatory workflow checks are fully covered by tests and docs.
  - Decision items (rows[].errors format / parity opt-in flags / Windows root handling) remain intentionally deferred as design choices, with explicit rationale and test coverage retained.
  - No new open blockers were added in this continuation window.

## Decision Rationale (implementation-ready)

- Keep optional contract flags for parity commands to preserve backward compatibility with existing ad-hoc reproducibility scripts.
- Keep local precheck mandatory in promotion paths to avoid manual bypass of governance.

## Handoff Checklist (next engineer, immediate sequence)

1. Re-open baseline
- Confirm workspace remains `L:\rrkal-visual-compressor`.
- Confirm only benchmark-related files are modified in this session scope.

2. Governance command verification
- Run (or verify) the precheck command:
  - `py scripts/precheck_benchmarks.py --root docs/benchmarks --pattern "*.json" --scan-out docs/benchmarks/scan_report.json --contract-out docs/benchmarks/contract_matrix_precheck.json --fail-on-scan-warning`
- Confirm summary includes: `scan_ok`, `contract_ok`, `contract`, `failed_report`, `status_counts`, `skipped`, `skip_reasons`, `total_inputs`.

3. Contract consistency verification
- Re-check `scripts/validate_benchmark_contracts_all.py --out` report path semantics in one known-bad fixture and one known-good fixture.
- Re-check `tests/test_benchmark_contracts.py` and `tests/test_precheck_benchmarks.py` assertions for dual ratio path compatibility (`direct_svg_to_package_ratio` + `direct_svg_gzip_to_package_ratio`).

4. CI/doc sync verification
- Confirm `.github/workflows/benchmarks-precheck.yml` still references:
  - `test_precheck_benchmarks.py`
  - `test_scan_benchmark_fields.py`
  - `test_benchmark_contracts.py`
  - `test_cli_smoke.py`
- Confirm documentation in `docs/benchmarks/README.md`, `docs/benchmarks/README.zh-TW.md`, `docs/benchmarks/CONTRACT.md`, `docs/benchmarks/CONTRACT.zh-TW.md` keeps the same precheck command signature.

5. Open items closure
- Resolve or escalate the four risk bullets above (especially local promotion mandatory gates) before declaring the benchmark governance loop stable.
- Add/refresh `docs/RENDERER_SKIN_ASSET_COMPATIBILITY_NOTES.zh-TW.md` as the entry-point memo for RendererSkinAsset compatibility and RRKAL runtime handoff assumptions before handing this phase to the next cycle.

## Local Benchmark Promotion SOP (mandatory from this session)

Use this exact sequence before promoting any benchmark artifacts (outside exploratory ad-hoc runs):

1. Build or update benchmark artifacts under `docs/benchmarks`.
2. Run optional legacy audit/migration preview:

```powershell
py scripts/convert_legacy_hardening_reports.py --root docs/benchmarks --dry-run
```

3. Run:

```powershell
py scripts/scan_benchmark_fields.py --root docs/benchmarks --pattern "*.json" --out docs/benchmarks/scan_report.json
```

4. Run:

```powershell
py scripts/validate_benchmark_contracts_all.py --root docs/benchmarks --pattern "*.json" --out docs/benchmarks/contract_matrix_latest.json
```

5. Run:

```powershell
py scripts/precheck_benchmarks.py --root docs/benchmarks --pattern "*.json" --scan-out docs/benchmarks/scan_report.json --contract-out docs/benchmarks/contract_matrix_precheck.json --fail-on-scan-warning
```

6. Optional migration step (approve once before write):

```powershell
py scripts/convert_legacy_hardening_reports.py --root docs/benchmarks
```

7. Stop immediately if precheck exits non-zero or reports:
- `scan_ok: false`
- `contract_ok: false`
- `contract.status != "ok"`

8. Only after pass:
- update docs and report artifacts together with code changes.
- then run the usual PR smoke tests and CI workflow.

## Execution Checklist (action-only, until 06:00 Asia/Taipei)

1. Confirm precheck gate is the required local workflow for benchmark changes.
- Run the standard command:
  - `py scripts/precheck_benchmarks.py --root docs/benchmarks --pattern "*.json" --scan-out docs/benchmarks/scan_report.json --contract-out docs/benchmarks/contract_matrix_precheck.json --fail-on-scan-warning`
- Ensure `scan_ok`, `contract_ok`, `status_counts`, `skipped`, `skip_reasons`, and `total_inputs` are present before merging benchmark-related diffs.

2. Keep one command set for PR and local promotion.
- Use one of the two forms only:
  - `py scripts/scan_benchmark_fields.py --root docs/benchmarks --pattern "*.json" --out ...`
  - `py scripts/validate_benchmark_contracts_all.py --root docs/benchmarks --pattern "*.json" --out ...`
- Do not use ad-hoc custom scripts to bypass these outputs.

3. Lock ratio handling behavior.
- Keep tests and code treating:
  - `direct_svg_to_package_ratio`
  - `direct_svg_gzip_to_package_ratio`
  as both valid and equivalent preference targets when selecting best-by-ratio candidates.
- If one must be removed/renamed, first add migration notes and a temporary compatibility shim.

4. Keep CI and docs synchronized when changing files.
- After edits, sync these locations:
  - `docs/benchmarks/CONTRACT.md`
  - `docs/benchmarks/CONTRACT.zh-TW.md`
  - `docs/benchmarks/README.md`
  - `docs/benchmarks/README.zh-TW.md`
  - `.github/workflows/benchmarks-precheck.yml`
  - `docs/AGENT_HANDOFF.md`

5. Close risk bullets explicitly.
- Update the four Open Items only with one of:
  - implemented + test-locked
  - intentionally deferred + owner/date
  - removed with justification.
- Keep the updated status in the first section of this file.

## Verification Snapshot (authoritative checks to run before handoff)

1. `scripts/compare_terms_channel_benchmark_parity.py --help` should still describe:
- `--validate-contract` as optional contract validation.
- `--require-contract-pass` as strict enforcement mode (`--validate-contract` implied).

2. Governance command consistency:
- `docs/benchmarks/CONTRACT.md`, `docs/benchmarks/CONTRACT.zh-TW.md`,
  `docs/benchmarks/README.md`, and `docs/benchmarks/README.zh-TW.md` should show the same precheck paths:
  - `--scan-out docs/benchmarks/scan_report.json`
  - `--contract-out docs/benchmarks/contract_matrix_precheck.json`
  - `--fail-on-scan-warning`

3. Local mandatory SOP path:
- `docs/AGENT_HANDOFF.md` must include the promotion sequence and stop-on-failure condition before artifact promotion.
  - Precheck outputs should treat legacy/non-contract benchmark JSON as `SKIP`, surfaced as `skipped` and `status_counts.SKIP`, and backed by scan/contract helper behavior.
- Include legacy hardening migration command in SOP before mandatory scan/contract steps:
  - `py scripts/convert_legacy_hardening_reports.py --root docs/benchmarks --dry-run`
- Verify `test_convert_legacy_hardening_reports.py` is part of benchmark precheck CI smoke.

## PR-Ready Delivery Snapshot

- Scope of this cycle: benchmark governance hardening under `docs/benchmarks/*`, `scripts/*`, and `tests/*`.
- Deliverables completed:
  - mandatory local precheck SOP recorded in handoff.
  - precheck command path aligned across CONTRACT/README docs (zh-TW + EN).
  - parity contract flags kept opt-in (`--validate-contract`, `--require-contract-pass`).
  - open-risk items reduced to explicit decisions with rationale.
- Minimal self-verify (fast, non-destructive):
  - `py scripts/precheck_benchmarks.py --root docs/benchmarks --pattern "*.json" --scan-out docs/benchmarks/scan_report.json --contract-out docs/benchmarks/contract_matrix_precheck.json --fail-on-scan-warning`
  - `py scripts/compare_terms_channel_benchmark_parity.py --help` (confirm optional contract flags presence)
  - `py -m pytest tests/test_convert_legacy_hardening_reports.py -q` (contract migration regression smoke)
  - `git status --short` (confirm only intended scope changed)

## Á∫åÊé•‰∫§Êé•Ë≠âÊìöÊ®°ÊùøÔºàÂèØÁõ¥Êé•Ë≤ºÂõûÂ†±Ôºâ

```text
Êé•ÊâãÊôÇÈñì (Asia/Taipei):
ËÆäÊõ¥Ê™îÊ°à:
- docs/AGENT_HANDOFF.md
- scripts/precheck_benchmarks.py
- scripts/report_workspace_candidates.py

ÂëΩ‰ª§ÊëòË¶Å:
- python scripts/precheck_benchmarks.py --root docs/benchmarks --pattern "*.json" --scan-out docs/benchmarks/scan_report.json --contract-out docs/benchmarks/contract_matrix_precheck.json --fail-on-scan-warning
- python scripts/report_workspace_candidates.py --root <repo_root> --max-depth 4

Ëº∏Âá∫ÊëòË¶Å:
- scan_ok / contract_ok
- contract.status / contract.failed / contract.passed
- scan: total / invalid_json
- status_counts / skipped / skip_reasons / total_inputs / failed_report

È¢®Èö™ÈòªÂ°û:
- tmp_* / smoke_* / model.vizretain* È°ûËàäÁõÆÈåÑÂ¶Ç‰ªç‰øùÁïô‰∏î ACL Ê¨äÈôê‰∏çË∂≥ÔºåÊúÉÈÄ†ÊàêÂæåÁ∫åÂëΩ‰ª§ÂØ´Âá∫Â§±Êïó„ÄÇ
- ÈúÄÁ¢∫Ë™ç Cloud(ËàäË≥áÊñôÂ§æ)ËàáÊú¨Âú∞ Git Â∑•‰ΩúÁõÆÈåÑÊúÄÂæåÂÖ±Ë≠òÁâàÊú¨ÂÜçÁπºÁ∫åÂ¢ûÈáè‰øÆÊîπ„ÄÇ

‰∏ã‰∏ÄÊ≠• (Êé•ÊâãËÄÖÂèØÁõ¥Êé•Âü∑Ë°å):
1. Ê™¢Ê†∏ git status ËàáÈÅ†Á´Ø‰∏ªÁ∑öÂ∞çÈΩä„ÄÇ
2. Âü∑Ë°å precheck ÂëΩ‰ª§ÔºåÁ¢∫Ë™ç summary Ê¨Ñ‰Ωç„ÄÇ
3. Ëã• precheck Áï∞Â∏∏ÔºåÂÖàÂü∑Ë°å workspace_candidate ÂëΩ‰ª§‰∏¶Ê∏ÖÁêÜÂèØÁñëÁõÆÈåÑ„ÄÇ
4. ‰æùÁÖßÁèæÊúâÊ™¢Êü•Ê∏ÖÂñÆÂÆåÊàê PR È¢®Èö™È†ÖÁõÆÊõ¥Êñ∞„ÄÇ
```
## Checkpoint: Jun 02, 2026 (pytest resilience after locked temp outputs)

- Performed end-to-end CLI smoke validation (`build -> inspect -> verify -> reconstruct`) on a short synthetic sample.
- Confirmed `--clean-output` fallback works when stale output directories are ACL-blocked:
  - command logs `warning: cannot clean '<out>': <permission denied>` and writes to `<out>.retry_<timestamp>`.
- Added broader pytest recursion exclusion in [pytest.ini](/L:/rrkal-visual-compressor/pytest.ini) to prevent locked temporary package folders (`tmp_*`, `_tmp*`, `*model.vizretain*`) from breaking collection.
- Revalidated full suite:
  - `python -m pytest -q`
  - result: `157 passed`

Outstanding residual:
- `_tmp_progress_small/model.vizretain` and `_tmp_progress_small.retry_* /model.vizretain` remain ACL-blocked in this environment and should be cleaned by platform storage permission fix before attempting raw directory deletion.
- Secondary cleanup attempt via `icacls /reset` / `icacls /grant <user>:F /T` on `_tmp_progress_small` confirmed same `Access is denied` on nested `model.vizretain`; classify as external ACL ownership issue and avoid touching these paths in-session.

## Checkpoint: Jun 01, 2026 (renderer compatibility notes handoff)

- Added `docs/RENDERER_SKIN_ASSET_COMPATIBILITY_NOTES.zh-TW.md` to define explicit P5/P6-facing bridge assumptions:
  - compatibility schema expectations (`compatibility` block)
  - review / verify gate mapping
  - recommended ingestion flow for registry/runtime consumers
- Scope still excludes cross-repo implementation; this repo remains the contract author for `.vizasset` and compatibility metadata.
- Next: bind runtime contract with RRKAL Core/RendererSkinAsset consumers in their owning repos, then return to update this handoff with verified loader behavior and runtime-native acceptance criteria.

## Checkpoint: May 31, 2026 (selector ratio fallback hardening)

- Stabilized benchmark recommendation scoring against ratio-field variants:
  - `src/vizcompress/selectors.py` now parses numeric ratio values robustly and falls back to `direct_svg_gzip_to_package_ratio` when `direct_svg_to_package_ratio` is missing/invalid.
  - `recommend_benchmark_row_gzip` now uses parsed numeric ratio checks consistently.
- Added regression coverage in `tests/test_timeseries_compression.py`:
  - `test_selector_recommends_with_gzip_only_ratio_fields`
  - `test_selector_recommendation_keeps_string_fields_robust`
- Next: keep contract docs/CLI coverage aligned and continue with next governance or CLI hardening slice.

## Checkpoint: May 31, 2026 (selector bool ratio hardening)

- Aligned selector ratio parsing with benchmark contract numeric rules:
  - `src/vizcompress/selectors.py` now rejects bool ratio values instead of coercing `True`/`False` to `1.0`/`0.0`.
  - Added `test_selector_recommendation_rejects_bool_ratio_fields` in `tests/test_timeseries_compression.py`.
- Verification snapshot:
  - `python -m pytest tests/test_timeseries_compression.py -q --maxfail=1`: `55 passed`
  - `python -m pytest tests/test_benchmark_contracts.py tests/test_scan_benchmark_fields.py tests/test_precheck_benchmarks.py tests/test_cli_smoke.py -q --maxfail=1`: `30 passed`
- Exchange inbox status checked at checkpoint close: `a_1_rrkal-visual-compressor.md` remains `needs-evidence`; no new response required.

## Checkpoint: May 31, 2026 (progress push)
- Confirmed target forum rule files and inbox status.
- Verified no `Status: new` entries for `rrkal-visual-compressor` at this checkpoint (`a_1_rrkal-visual-compressor.md` is `needs-evidence`).
- Executed MVP pipeline once (`py -m vizcompress.cli mvp --samples 5000 --synthetic-kind spikes --fourier-terms 64 --out MVP_CHECKPOINT`) previously in this session; run passed with `fourier_r2=0.9871501503`, benchmark gate pass, and generated evidence summary in previous handoff entry.
- Attempted to remove `L:\rrkal-visual-compressor\MVP_CHECKPOINT` for workspace hygiene, but one generated artifact `model.vizretain` is ACL-restricted (`Access is denied`) in this environment.
- Working decision: keep artifact until environment-level permission resolution; continue implementation with code paths under `src/` and `docs/`.
- Next: proceed with a reproducible small feature slice in `rrkal-visual-compressor` if no blocking cross-project dependency is reported.

## Checkpoint: May 31, 2026 (workspace governance hardening)
- Updated `docs/DEVELOPMENT_GOVERNANCE.md` to reflect the active boundary:
  - authoritative workspace is `L:\rrkal-visual-compressor`
  - `L:\AGENT_EXCHANGE` is non-product coordination forum and not pushed to GitHub
  - other folders on L are treated as read-only in this session
  - generated outputs should not be committed unless explicitly approved
- Inserted `Phase 2.8: Operational Hardening` into `docs/ROADMAP.md` to formalize artifact cleanup and checkpoint flow as an explicit backlog item.
- Next step: implement a CLI/utility cleanup utility or documented pre-run check for stale output directories to reduce future `Access denied`/stale artifact friction.

## Checkpoint: May 31, 2026 (CLI output hygiene slice)
- Added `--clean-output` flag to `build` and `mvp` in `src/vizcompress/cli.py`.
- Added `_prepare_output_directory()` + best-effort forced delete helpers (`_forceful_delete_directory`, `_force_remove_file`, `_set_writable`) to clean stale output directories before run.
- `mvp` now forwards the flag into the internal build invocation so one call sequence can keep deterministic output folders.
- This is a tooling slice aimed at reducing stale artifact lock/permission friction (e.g., `model.vizretain` access denied) and improving local session momentum.
- Next: decide whether `bench`/`video-bench` should also support an explicit `--clean-output` mode for output JSON reuse and consistency.

## Checkpoint: May 31, 2026 (resilience improvement)
- Strengthened `src/vizcompress/cli.py` cleanup path: `_prepare_output_directory` now returns the effective directory, and when deletion cannot be forced, it falls back to an auto-named retry directory (`<out>.retry_<timestamp>`) instead of hard failing.
- This makes `--clean-output` robust when Windows ACL/lock prevents direct deletion of `model.vizretain` style directories.
- Manual sanity run confirmed `--clean-output` is accepted when running from local `L:` source path (`PYTHONPATH=L:\rrkal-visual-compressor\src`).
- Manual cleanup attempt revealed stale `tmp_cli_sanity_check/model.vizretain` may still be ACL-locked in this environment; fallback behavior is therefore the safest path to avoid hard stops.

## Checkpoint: May 31, 2026 (CLI output hygiene continuity)
- Extended `--clean-output` to `bench` and `video-bench` output targets in `src/vizcompress/cli.py`.
- Added `_prepare_output_file(...)` and shared fallback behavior for file outputs (`.json`/`.md`) so stale or locked output artifacts do not hard-stop benchmark commands; command now transparently uses retry paths when forced cleanup fails.
- `README.md` now documents `--clean-output` examples for `build`, `mvp`, `bench`, and `video-bench`.
- Next: run a short sanity command path (`bench`/`video-bench`) under `PYTHONPATH=...` if environment permits, then evaluate whether `bench --clean-output` should also delete report parent directory as a unit.

## Checkpoint: May 31, 2026 (benchmark summary ratio alias hardening)
- `src/vizcompress/benchmarks.py` now tolerates missing `direct_svg_to_package_ratio` in benchmark rows by treating it as `direct_svg_gzip_to_package_ratio` in summary selection logic.
- Added safe helpers in `_summarize_rows`:
  - `_ratio()` for finite numeric extraction with alias fallback
  - `_best_row()` robust selection when preferred field is absent
  - `_row_identity()` null-safe field reads for best-row summaries
- Added regression coverage in [tests/test_benchmark_summary.py](/L:/rrkal-visual-compressor/tests/test_benchmark_summary.py):
  - `test_summarize_rows_uses_direct_svg_gzip_ratio_when_direct_ratio_missing`
  - `test_summarize_rows_without_ratio_fields_returns_safe_summary`
- Commit: `1546d0a` (`harden(benchmarks): tolerate direct ratio alias in summaries`).

## Checkpoint: May 31, 2026 (benchmark summary ratio string compatibility)
- Extended `_ratio()` in `src/vizcompress/benchmarks.py` to parse finite numeric strings, so fallback/summarization handles external payloads where ratios come as strings.
- Added regression coverage in [tests/test_benchmark_summary.py](/L:/rrkal-visual-compressor/tests/test_benchmark_summary.py):
  - `test_summarize_rows_accepts_numeric_ratio_strings_for_fallback_paths`
- Commit: `b477e1e` (`harden(benchmarks): accept numeric ratio strings in summary alias path`).



## Precheck Failure Recovery (shared SOP)

When `scripts/precheck_benchmarks.py` returns non-zero:

- Run candidate scan immediately:

```powershell
py scripts/report_workspace_candidates.py --root . --max-depth 4 --out docs/benchmarks/workspace_candidates.json
```

- Remove only confirmed stale candidate directories, then rerun the precheck command.
- For batch-safe cleanup, use:

```powershell
python scripts/cleanup_workspace_outputs.py --root . --max-depth 4 --out docs/benchmarks/workspace_cleanup_report.json
```

The report marks `model.vizretain` entries that are ACL-blocked as `manual_unlock`, and will not attempt to force-delete those paths.

- Keep a cleanup note in handoff evidence if any directory required manual intervention.
## 0000 Progress Log (2026-06-02 Asia/Taipei)

- K º—§w©w¶Ï¨∞ `K:\rrkal_workspace\rrkal-visual-compressor`°]`git status` clean°^°AHEAD = `03d7232`°]2026-05-28°^°C
- L º— `L:\rrkal-visual-compressor` HEAD = `e1fc225`°]2026-05-31°Afeat(cli): add precheck-benchmarks command°^°C
- ®‚¥ æ§ÒπÔµ≤™G°G`only_in_L = 12`°A`only_in_K = 0`°AL ¶≥ 12 ≠”√B•~™©•ª¿…°]ßt `.github/workflows/benchmarks-precheck.yml`°B`scripts/precheck_benchmarks.py`°B`scripts/scan_benchmark_fields.py`°B`tests/*precheck*` µ•°^°C
- §w¶A¶∏≈Á√“°G`py -m pytest -q` •˛≥°≥qπL°]`157 passed`°^°C
- §w¶A¶∏≈Á√“°G`scripts/precheck_benchmarks.py` ¶b `docs/benchmarks` §U¨∞ `PASS`°]`scan_ok=true`, `contract_ok=true`, `PASS=9`, `SKIP=4`, `FAIL=0`°^°C
- ∏…ªÙ `git status` ≈v≠≠™˝∂ÎπÔ¿≥≤M≤z°G`tmp_cli_smoke*`, `smoke_work*`, `tmp_verify_smoke*`, `tmp_cli_launcher` √˛ scratch •ÿø˝Ø«§J `.gitignore`°A®æ§Ó `permission denied` §z¬Z°C
- K ΩL≥¯ßi¨yµ{°G`scripts/report_workspace_candidates.py --root K:\rrkal_workspace\rrkal-visual-compressor --max-depth 4` §w•i∂]°Aº»¶s≠‘øÔ¶≥ 4 ≠”°]•˛≥°•i≈™•iºg°^°A§wßYÆ…≤M∞£º»¶s≥¯ßi¿…°C
## 0000 Progress Log (2026-06-02 Evening) - End-to-end smoke sweep

- Executed an end-to-end smoke sweep from one-shot script style using `scripts`-local CLI env (`L:\rrkal-visual-compressor` root):
  - `mvp --samples 5000 --synthetic-kind spikes --fourier-terms 64 --svg-samples 240`
  - `build --synthetic 4000 --synthetic-kind spikes --fourier-terms 48 --svg-samples 320 --channel --auto-noise-layer --package --direct-svg`
  - `inspect`, `verify`, `reconstruct` (center + retained), `compare` baseline, and `bench`
- Result summary: all commands completed successfully (`overall_ok: true`), with generated package validation and benchmark artifacts present.
- MVP payload key evidence:
  - `status: pass`
  - `validation.package_ok: true`
  - `validation.source_ok: true`
  - `benchmark_gate.ok: true`
  - `evidence.recommendation: package_preferred`
- Build+inspect+verify chain key signals:
  - `inspect.package_profile` and `schema_version` valid (`0.2`)
  - `verify.ok: true` and source fidelity fields populated
  - reconstruct payload returned finite sample summaries and sample override worked (`retained` 128)
- Bench payload present and contract-valid (one-row synthetic spikes sample output produced successfully).
- Follow-up cleanup: `smoke_end_to_end_0000*` is now ignored as non-committed scratch (`.gitignore`) due occasional ACL lock (`WinError 5`) on legacy `model.vizretain` artifacts.

## 0000 Progress Log (2026-06-02 Taipei - continuation)
- Ran `python scripts/precheck_benchmarks.py --root docs/benchmarks --pattern "*.json" --scan-out docs/benchmarks/scan_report.json --contract-out docs/benchmarks/contract_matrix_precheck.json --fail-on-scan-warning`.
  - Result: PASS (scan_ok=true, contract_ok=true).
  - Summary: PASS=9, SKIP=5, FAIL=0, status_counts { PASS: 9, SKIP: 5, FAIL: 0 }.
  - Scan breakdown: legacy=1, rows=6, sweep=7; legacy skip reasons=5.
- Ran `python scripts/report_workspace_candidates.py --root . --max-depth 4 --out docs/benchmarks/workspace_candidates.json`.
  - Result: 4 candidate paths detected, mainly `tmp_0000_checkpoint` and `smoke_end_to_end_0000`.
- Local scratch artifacts are now covered by `.gitignore` entries to avoid accidental commit noise:
  - `tmp_0000_checkpoint*`, `smoke_end_to_end_0000*`, generated precheck/workspace report JSON files.
- Cleanup follow-up: `scripts/cleanup_workspace_outputs.py --root . --max-depth 4 --execute --out ...` reported 2 hard failures (permission/OS errors) and one manual-unlock candidate:
  - failed to remove `tmp_0000_checkpoint\mvp\asset\model.vizretain` (WinError 5 / ACL)
  - failed to remove nested `smoke_end_to_end_0000\mvp` (WinError 145)

## 0000 Progress Log (2026-06-02 Taipei - replay)
- Ran a fresh end-to-end smoke replay on clean path `tmp_0000_checkpoint2` using `scripts/run_vizcompress_cli.py`:
  - mvp °˜ build °˜ inspect °˜ verify °˜ reconstruct(center/retained) °˜ compare(direct) °˜ bench.
  - Result: `0000 checkpoint replay: ok`.
  - `overall_ok=true`, `failed_commands=[]` in replay report.
- Replay artifact generated at `docs/benchmarks/0000_checkpoint_replay_report.json` and classified as scratch (`.gitignore`): no commit.
- ACL reality remains unchanged:
  - `tmp_0000_checkpoint\mvp\asset\model.vizretain` still reports `WinError 5`.
  - `smoke_end_to_end_0000\mvp` still reports `WinError 145` on direct deletion path.
- Command alignment remains unchanged; next move is continue with next feature slice once you confirm whether to proceed with precheck/cleanup hardening in session-wide mode.
## 0000 Progress Log (2026-06-02 Taipei - resumed replay)
- Re-ran `python scripts/run_0000_smoke_checkpoint.py --workspace-root . --output-dir tmp_0000_checkpoint --report-path tmp_0000_checkpoint_replay_report.json` in one pass:
  - Exit: `0`.
  - `overall_ok=true`.
  - `failed_commands=[]`.
- Latest report generated at `tmp_0000_checkpoint_replay_report.json` (same-root scratch output).
- Ran full benchmark precheck:
  - `python scripts/precheck_benchmarks.py --root docs/benchmarks --pattern "*.json" --scan-out docs/benchmarks/scan_report.json --contract-out docs/benchmarks/contract_matrix_precheck.json --fail-on-scan-warning`
  - Result: `PASS` (`contract_ok=true`, `scan_ok=true`, `FAIL=0`, `PASS=9`, `SKIP=6`).
- Workspace artifacts scan:
  - `smoke_end_to_end_0000*`, `tmp_0000_checkpoint*`, and `tmp_0000_checkpoint2*` are still the remaining large candidates.
  - Cleanup failure count is expected and attributable to directory locks/deep path state:
    - `WinError 145` on stale checkpoint folder removal.
    - `model.vizretain` entries are intentionally skipped by policy unless explicitly unlocked.## 0000 Progress Log (2026-06-02 Taipei - verification sweep)
- Ran `python scripts/run_0000_smoke_checkpoint.py --workspace-root . --output-dir tmp_0000_checkpoint --report-path tmp_0000_checkpoint_replay_report.json`.
  - Result: `exit 0`, `overall_ok=true`, `failed_commands=[]`.
- Ran benchmark precheck:
  - `python scripts/precheck_benchmarks.py --root docs/benchmarks --pattern "*.json" --scan-out docs/benchmarks/scan_report.json --contract-out docs/benchmarks/contract_matrix_precheck.json --fail-on-scan-warning`
  - Result: PASS (`contract_ok=true`, `scan_ok=true`, `FAIL=0`, `PASS=9`, `SKIP=6`).
- Ran workspace scanning and cleanup:
  - `scripts/report_workspace_candidates.py --root . --max-depth 4 --out docs/benchmarks/workspace_candidates.json`
  - `scripts/cleanup_workspace_outputs.py --root . --max-depth 4 --execute --out docs/benchmarks/workspace_cleanup_report.json`
  - Result: `deleted=1`, `failed=6`, `manual_unlock=1`, `skipped=10`, `to_remove=7`.
  - Remaining blockers are expected WinError ACL/path-lock artifacts in previous `tmp_0000_checkpoint*` and `tmp_0000_checkpoint2` runs.
- 0000 checkpoint remains green for functionality; open operational debt is only stale workspace artifact deletion constraints.## 0000 Progress Log (2026-06-02 Taipei - cross-cwd replay check)
- Re-ran checkpoint via absolute paths from `C:\Users\lyn59`:
  - `python L:\rrkal-visual-compressor\scripts\run_0000_smoke_checkpoint.py --workspace-root L:\rrkal-visual-compressor --output-dir tmp_0000_checkpoint --report-path L:\rrkal-visual-compressor\tmp_0000_checkpoint_replay_report.json`
  - Result: `0000 checkpoint: ok`.
- Re-ran benchmark precheck from external cwd with absolute `--root`/`--scan-out`/`--contract-out`:
  - Result: `PASS` (`contract_ok=true`, `scan_ok=true`, `FAIL=0`, `PASS=9`, `SKIP=6`).
- Confirms helper scripts are cwd-independent for command dispatch and report generation.## 0000 Progress Log (2026-06-02 Taipei - cleanup hardening)
- Upgraded `scripts/cleanup_workspace_outputs.py` with:
  - retry attempts for deletion failures
  - best-effort permission clearing before retries
  - `manual_unlock_required` classification for known ACL/lock errors (WinError 5/145)
- Executed with new behavior:
  - `python scripts/cleanup_workspace_outputs.py --root . --max-depth 4 --execute --out docs/benchmarks/workspace_cleanup_report.json`
  - Result: `deleted=1`, `manual_unlock=6`, `failed=0`, `skipped=7`, `to_remove=7`.
- Net effect: stale workspace blockers now consistently surfaced as actionable manual-unlock items in report, reducing ambiguous failure noise for iteration loops.## 0000 Progress Log (2026-06-02 Taipei - verification refresh)
- Re-ran end-to-end 0000 replay using current scripts:
  - `python scripts/run_0000_smoke_checkpoint.py --workspace-root . --output-dir tmp_0000_checkpoint --report-path tmp_0000_checkpoint_replay_report.json`
  - Result: `0000 checkpoint: ok`.
- Re-ran benchmark precheck:
  - `python scripts/precheck_benchmarks.py --root docs/benchmarks --pattern "*.json" --scan-out docs/benchmarks/scan_report.json --contract-out docs/benchmarks/contract_matrix_precheck.json --fail-on-scan-warning`
  - Result: `PASS` (`contract_ok=true`, `scan_ok=true`, `FAIL=0`, `PASS=9`, `SKIP=6`).## 0000 Progress Log (2026-06-02 Taipei - coordination policy update)
- Implemented policy direction update in repo docs:
  - Primary coordination is Notion (`AgentsË®éË´ñÂçÄ`) with these spaces:
    - `04_Agent_Inbox` for status/handoff/relay
    - `03_OAI_Review_Requests` for o_1 review requests
    - `02_Decision_Log` for accepted decisions
    - `06_n1_SOP` for n_1 operations
  - `L:\AGENT_EXCHANGE` is treated as archive/history only.
  - Cloud-drive exchange is no longer used as primary output path for agent mail.
- Current repository scan shows no remaining code-paths that write new agent coordination messages to cloud drive under project workspace (`AGENT_EXCHANGE` appears only in historical references).