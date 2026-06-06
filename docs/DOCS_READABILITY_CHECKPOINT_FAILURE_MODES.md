# Docs Readability Checkpoint Failure Modes and Troubleshooting Index

This index records common failures observed in checkpoint operations and a bounded
first-response workflow. It is for docs-readability lane stabilization only.

## Scope and non-goals

- Scope: checkpoint command topology, leaf/meta test separation, subprocess timeout,
  process fan-out visibility, and JSON payload integrity.
- Non-goals:
  - .vizasset manifest/schema edit
  - CLI behaviour changes
  - compression algorithm changes
  - cross-repo implementation

## 1) Failure mode index (lookup by symptom)

| ID | Symptom | Likely cause | Immediate check | Typical mitigation |
| --- | --- | --- | --- | --- |
| F-001 | `checkpoint_passed=False` but command still exits 0 in scripts | Runner/validator command mismatch | rerun with `python scripts/docs_readability_checkpoint.py --json | python -c ...` | align test expectations with required booleans and re-check required fields |
| F-002 | `schema` mismatch | stale script/docs contract drift | print payload `schema` and compare against `docs-readability-checkpoint/v1` | update docs/index pair in one lane only |
| F-003 | `status` is `fail` | one or more required booleans false | inspect `readability_pytest_passed` and other booleans | fix dirty docs/text evidence first, avoid touching scripts/tests |
| F-004 | `clean_docs_scan_passed=false` | decode/marker regression in touched docs | run checker self-scan; re-run on target docs files | repair artifact text before further docs edits |
| F-005 | fixture strict mode not warning | negative fixture regression or command path drift | run `--strict` against `contains_fffd.md` and `contains_pua.md` | restore fixture contract and scanner option path |
| F-006 | `c2_python_process_count` rises unexpectedly | recursive fan-out in checkpoint/validator chain | check `c2_python_process_samples` and process list | enforce leaf-only execution and remove meta-call from runner |
| F-007 | subprocess timeout hit | missing timeout/longer command chain | inspect wall-clock and command chain | keep command timeout at 30s and reduce nested runner fan-out |
| F-008 | JSON output polluted by logs | text prints added in JSON mode | test pure parse with `json.load(sys.stdin)` | keep logs to stderr or gated by non-JSON mode |
| F-009 | recursive meta-test recursion | validator path enters checkpoint meta tests | confirm `test_leaf_` filter is active | checkpoint should only invoke `test_leaf_*` and env marker |

## 2) Escalation sequence (do not skip)

1. Capture raw checkpoint run:
   - `python scripts/docs_readability_checkpoint.py --json | python -c "import sys,json; d=json.load(sys.stdin); assert d['checkpoint_passed'] is True"`
2. If fail, run validator self-test:
   - `python scripts/validate_docs_readability_checkpoint.py --self-test-negative`
3. Check direct tests:
   - `python -m pytest tests/test_docs_readability_checker.py -q`
4. Confirm command-line entry points:
   - `python -m vizcompress --help`
   - `python -m vizcompress.cli --help`
5. Confirm readability guard on touched docs:
   - `python scripts/check_docs_readability.py scripts/check_docs_readability.py docs/AGENT_START_HERE.zh-TW.md docs/AGENT_HANDOFF.md docs/C2_QUICK_STARTUP_DELIVERY_SOP.md`

## 3) Recursive fan-out incident checklist

Observed pattern:
- checkpoint command -> pytest -> meta tests -> validator -> checkpoint -> pytest ...

Prevention checks:
- checkpoint runner must enforce `-k test_leaf_`.
- runner must not invoke meta-test entry points.
- validator may invoke checkpoint for contract checks.
- process count should be collected and reviewed (`c2_python_process_count`).

Stop condition:
- recursive chain remains after these guards and `c2_python_process_count` continues to increase.

## 4) Timeout policy

- default timeout target: 30 seconds per subprocess path (checkpoint / validator / scanner).
- If exceeded, treat as topology/chain risk and stop lane adjustments.

## 5) Required checkpoints for docs-readability lane closure

- JSON payload keys: all required fields present.
- `status == \"pass\"` and `checkpoint_passed == true`.
- leaf/meta split verified.
- `c2_python_process_count` recorded.
- `U+FFFD` / PUA warning behaviour remains consistent for fixtures.

## 6) Reporting template for this lane

- Repo, branch, head
- command results and pass/fail
- fault mode ID if triggered
- fix action taken
- process evidence (`c2_python_process_count`, PID/CMD samples when non-zero)
- boundary statement

Boundary note:
- This index is for internal docs-readability readiness and does not grant downstream consumption intent.
