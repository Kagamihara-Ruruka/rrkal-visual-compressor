---
title: Docs Readability Checkpoint Contract
scope: L2 checkpoint/docs-readability lane
version: v1
---

# Docs Readability Checkpoint Contract (L2)

This document is a documentation-index contract for c_2 docs-readability tasks.
It records what a checkpoint run must produce and what each layer may consume.

## 1. Purpose

- Stabilize the docs-only readability workflow after recursive checkpoint/validator incidents.
- Define a bounded contract surface so checkpoint output is machine-parseable.
- Separate leaf evidence from meta checks and keep execution topology one-way.
- Keep boundary claims explicit and minimal.

## 2. Contract schema and required evidence fields

- Contract schema: `docs-readability-checkpoint/v1`
- Status model:
  - `pass` means all required booleans are `true`.
  - `fail` means at least one required boolean is `false`.

### Required top-level fields

| Field | Meaning | Producer | Must be true |
| --- | --- | --- | --- |
| `schema` | Checkpoint payload version | `docs_readability_checkpoint.py --json` | string fixed to `docs-readability-checkpoint/v1` |
| `status` | Overall result token | `docs_readability_checkpoint.py --json` | must be `pass` |
| `clean_docs_scan_passed` | UTF-8 / marker scan for target docs succeeded | `docs_readability_checkpoint.py --json` | true |
| `negative_fixture_detection_passed` | Negative fixtures detect issues in strict mode | `docs_readability_checkpoint.py --json` | true |
| `cli_help_passed` | Repo entry commands are functional | `docs_readability_checkpoint.py --json` | true |
| `no_manifest_schema_change` | No manifest/schema edits in working tree diff vs `HEAD` | `docs_readability_checkpoint.py --json` | true |
| `readability_pytest_passed` | Leaf docs-readability tests passed | `docs_readability_checkpoint.py --json` | true |
| `checkpoint_passed` | Combined gate | computed | true |
| `c2_python_process_count` | Process fan-out evidence | `docs_readability_checkpoint.py --json` | integer, non-negative |

### Required boundary fields

| Field | Meaning | Expected |
| --- | --- | --- |
| `boundary.no_manifest_schema_change_required` | Scope constraint remains active | true |
| `boundary.cli_behavior_unchanged` | CLI behavior is untouched by this lane | true |
| `boundary.algorithm_unchanged` | Compression logic untouched by this lane | true |
| `boundary.cross_repo_integration_not_touched` | No cross-repo implementation by this lane | true |
| `boundary.leaf_tests_only` | Runner executes leaf tests only | true |
| `boundary.recursion_guard_set` | Checkpoint runner has recursion guard | true |

## 3. Layered test map (leaf / meta)

### Leaf layer (`test_leaf_*`)

- `test_leaf_readability_checker_accepts_clean_fixture`
- `test_leaf_readability_checker_warns_on_fffd_marker`
- `test_leaf_readability_checker_warns_on_pua_marker`

These are direct evidence generators for:
- UTF-8 and marker scan behaviour
- warning presence in negative fixtures
- pytest execution within docs-touching scope

### Meta layer (`test_meta_*`)

- `test_meta_docs_readability_checkpoint_json_output_is_pure_json`
- `test_meta_validate_docs_readability_checkpoint_script`
- `test_meta_validate_docs_readability_checkpoint_self_test_negative`
- `test_meta_checkpoint_internal_pytest_uses_leaf_tests_only`

Meta layer is non-aggregating and may validate:
- JSON purity constraints
- validator logic
- topology of leaf/meta split

### Checkpoint contract rule

- Checkpoint execution must call:
  - `pytest` with `-k test_leaf_ --maxfail=1`
  - environment marker for checkpoint mode
- Validator must never be invoked inside checkpoint execution.
- Validator may invoke checkpoint to verify output.

## 4. Timeout and process fan-out contract

- Subprocess timeout target: **30s** for checkpoint and validator command path.
- `c2_python_process_count` must be recorded after run.
- If count exceeds warning limit, emit explicit warning in log/report.
- Persistent or explosive process growth is a stop condition.

## 5. Negative fixture contract

- Clean target:
  - `tests/fixtures/docs_readability/clean.md` should not produce soft failures.
- Negative targets:
  - `tests/fixtures/docs_readability/contains_fffd.md` must trigger:
    - `U+FFFD present`
  - `tests/fixtures/docs_readability/contains_pua.md` must trigger:
    - `PUA chars found`
- Strict mode should return warning / non-zero exit for these files.

## 6. Required command inventory for this contract

- `python scripts/docs_readability_checkpoint.py --json`
- `python scripts/validate_docs_readability_checkpoint.py`
- `python scripts/validate_docs_readability_checkpoint.py --self-test-negative`
- `python -m pytest tests/test_docs_readability_checker.py -q`
- `python -m vizcompress --help`
- `python -m vizcompress.cli --help`
- `python scripts/check_docs_readability.py scripts/check_docs_readability.py docs/AGENT_START_HERE.zh-TW.md docs/AGENT_HANDOFF.md docs/C2_QUICK_STARTUP_DELIVERY_SOP.md`
- `git diff --check`

## 7. Non-consumption boundary (scan-safe language)

This contract is documentation/evidence-only support for local lane operations.
It is not a cross-repo schema promise, and it does not encode product adoption status.

## 8. Versioning and maintenance

- Owner in this lane: c_2
- Review touchpoints:
  - Notion coordination lanes for decisions
  - o_1 for cross-boundary approvals
- Update only when contract field list, timeout policy, or topology changes.
