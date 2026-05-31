from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from _test_helpers import run_cli


def _run_precheck(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "vizcompress.cli", "precheck-benchmarks", *argv]
    return run_cli(cmd, **kwargs)


def assert_precheck_summary_shape(payload: dict) -> None:
    assert set(
        [
            "schema_version",
            "scan_ok",
            "contract_ok",
            "scan_report",
            "contract_report",
            "scan",
            "contract",
            "failed_report",
            "status_counts",
            "skipped",
            "skip_reasons",
            "total_inputs",
            "skip_scan",
            "skip_contract",
            "root",
            "pattern",
        ]
    ).issubset(payload)


def test_precheck_benchmarks_fails_on_scan_violation(tmp_path: Path) -> None:
    root = tmp_path / "benchmarks"
    root.mkdir()
    good = root / "good.json"
    bad = root / "bad.json"
    good.write_text(
        json.dumps(
            {
                "benchmark": "good",
                "rows": [
                    {
                        "synthetic_kind": "spikes",
                        "samples": 1000,
                        "fourier_terms": 16,
                        "fourier_r2": 0.99,
                        "direct_svg_to_package_ratio": 1.1,
                        "direct_svg_gzip_to_package_ratio": 1.0,
                        "source_csv_gzip_to_package_ratio": 1.0,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    bad.write_text(
        json.dumps(
            {
                "benchmark": "bad",
                "rows": [
                    {
                        "synthetic_kind": "spikes",
                        "samples": 1000,
                        "fourier_terms": 16,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = _run_precheck(
        [
            "--root",
            str(root),
            "--pattern",
            "*.json",
            "--scan-out",
            str(root / "scan.json"),
            "--contract-out",
            str(root / "contract.json"),
            "--fail-on-scan-warning",
            "--skip-contract",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["scan_ok"] is False


def test_precheck_benchmarks_fails_on_unreadable_scan_payload(tmp_path: Path) -> None:
    root = tmp_path / "benchmarks"
    root.mkdir()
    broken = root / "bad_encoding.json"
    broken.write_bytes(b"\xff\x00\xfe")

    result = _run_precheck(
        [
            "--root",
            str(root),
            "--pattern",
            "*.json",
            "--scan-out",
            str(root / "scan.json"),
            "--contract-out",
            str(root / "contract.json"),
            "--skip-contract",
            "--fail-on-scan-warning",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["scan_ok"] is False
    assert payload["scan"]["invalid_json"] == 1


def test_precheck_benchmarks_summary_schema_is_stable(tmp_path: Path) -> None:
    root = tmp_path / "benchmarks"
    root.mkdir()
    root.joinpath("ok.json").write_text(
        json.dumps(
            {
                "benchmark": "ok",
                "rows": [
                    {
                        "synthetic_kind": "spikes",
                        "samples": 1000,
                        "fourier_terms": 16,
                        "fourier_r2": 0.99,
                        "direct_svg_to_package_ratio": 1.1,
                        "direct_svg_gzip_to_package_ratio": 1.0,
                        "source_csv_gzip_to_package_ratio": 1.0,
                    }
                ],
                "summary": {
                    "high_fidelity_rows_count": 1,
                    "defensible_rows_count": 0,
                    "defensible_rows_ratio": 0.0,
                    "defensible_channel_coverage_threshold": 0.9,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = _run_precheck(
        [
            "--root",
            str(root),
            "--pattern",
            "*.json",
            "--scan-out",
            str(root / "scan.json"),
            "--contract-out",
            str(root / "contract.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert_precheck_summary_shape(payload)
    assert payload["scan_report"] == str(root / "scan.json")
    assert payload["contract_report"] == str(root / "contract.json")
    assert payload["schema_version"] == "1.0"
    assert payload["skip_scan"] is False
    assert payload["skip_contract"] is False
    assert payload["contract"]["status"] == "ok"
    assert payload["total_inputs"] == 1


def test_precheck_benchmarks_rejects_both_skip_flags(tmp_path: Path) -> None:
    root = tmp_path / "benchmarks"
    root.mkdir()
    root.joinpath("ok.json").write_text(
        json.dumps({"benchmark": "ok", "rows": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    result = _run_precheck(
        [
            "--root",
            str(root),
            "--pattern",
            "*.json",
            "--scan-out",
            str(root / "scan.json"),
            "--contract-out",
            str(root / "contract.json"),
            "--skip-scan",
            "--skip-contract",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    combined_output = (result.stdout or "") + (result.stderr or "")
    assert "cannot skip both scan and contract validation" in combined_output


def test_precheck_benchmarks_contract_failure_sets_failed_report(tmp_path: Path) -> None:
    root = tmp_path / "benchmarks"
    root.mkdir()
    root.joinpath("bad.json").write_text(
        json.dumps(
            {
                "benchmark": "bad",
                "rows": [
                    {
                        "synthetic_kind": "spikes",
                        "samples": -10,
                        "fourier_terms": 64,
                        "fourier_r2": 0.99,
                        "source_csv_gzip_to_package_ratio": 1.0,
                        "direct_svg_gzip_to_package_ratio": 1.1,
                        "direct_svg_to_package_ratio": 1.0,
                    }
                ],
                "summary": {
                    "high_fidelity_rows_count": 1,
                    "defensible_rows_count": 0,
                    "defensible_rows_ratio": 0.0,
                    "defensible_channel_coverage_threshold": 0.95,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = _run_precheck(
        [
            "--root",
            str(root),
            "--pattern",
            "*.json",
            "--scan-out",
            str(root / "scan.json"),
            "--contract-out",
            str(root / "contract.json"),
            "--skip-scan",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["contract"]["status"] == "fail"
    assert payload["failed_report"] == str(root / "contract.json")


def test_precheck_benchmarks_contract_success_with_skip_scan(tmp_path: Path) -> None:
    root = tmp_path / "benchmarks"
    root.mkdir()
    contract_ok_file = root / "ok.json"
    contract_ok_file.write_text(
        json.dumps(
            {
                "benchmark": "ok",
                "rows": [
                    {
                        "synthetic_kind": "spikes",
                        "samples": 1000,
                        "fourier_terms": 16,
                        "channel_k": 2.0,
                        "fourier_r2": 0.99,
                        "direct_svg_to_package_ratio": 1.1,
                        "direct_svg_gzip_to_package_ratio": 1.0,
                        "source_csv_gzip_to_package_ratio": 1.0,
                    }
                ],
                "summary": {
                    "high_fidelity_rows_count": 1,
                    "defensible_rows_count": 0,
                    "defensible_rows_ratio": 0.0,
                    "defensible_channel_coverage_threshold": 0.9,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = _run_precheck(
        [
            "--root",
            str(root),
            "--pattern",
            "*.json",
            "--scan-out",
            str(root / "scan.json"),
            "--contract-out",
            str(root / "contract.json"),
            "--skip-scan",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["contract_ok"] is True
    assert payload["scan_ok"] is True
    assert payload["contract"]["status"] == "ok"
    assert payload["scan"] == {}
    assert payload["status_counts"]["PASS"] == 1
    assert payload["status_counts"].get("SKIP", 0) == 0
    assert payload["skipped"] == 0
    assert payload["skip_scan"] is True
    assert payload["total_inputs"] == 1
    assert payload["scan_report"] == str(root / "scan.json")
    assert payload["contract_report"] == str(root / "contract.json")


def test_precheck_benchmarks_help_includes_benefit_flags() -> None:
    result = _run_precheck(
        [
            "--help",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    output = result.stdout
    assert "--skip-scan" in output
    assert "--skip-contract" in output
    assert "--fail-on-scan-warning" in output
    assert "--scan-out" in output
    assert "--contract-out" in output


def test_precheck_benchmarks_contract_skipped_reports_contract_defaults(tmp_path: Path) -> None:
    root = tmp_path / "benchmarks"
    root.mkdir()
    root.joinpath("ok.json").write_text(
        json.dumps(
            {
                "benchmark": "ok",
                "rows": [
                    {
                        "synthetic_kind": "spikes",
                        "samples": 1000,
                        "fourier_terms": 16,
                        "fourier_r2": 0.99,
                        "direct_svg_to_package_ratio": 1.1,
                        "source_csv_gzip_to_package_ratio": 1.0,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = _run_precheck(
        [
            "--root",
            str(root),
            "--pattern",
            "*.json",
            "--scan-out",
            str(root / "scan.json"),
            "--contract-out",
            str(root / "contract.json"),
            "--skip-contract",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["contract"] == {"status": "not_run", "failed": 0, "passed": 0, "total": 0}
    assert payload["contract_report"] == str(root / "contract.json")
    assert payload["status_counts"] == {}
    assert payload["skipped"] == 0
    assert payload["skip_reasons"] == {}
    assert payload["scan"]["total"] == 1
    assert payload["total_inputs"] == 1


def test_precheck_benchmarks_contract_skips_row_payload_missing_row_summary_counters(tmp_path: Path) -> None:
    root = tmp_path / "benchmarks"
    root.mkdir()
    root.joinpath("legacy_rows.json").write_text(
        json.dumps(
            {
                "benchmark": "legacy_rows",
                "rows": [
                    {
                        "synthetic_kind": "spikes",
                        "samples": 1000,
                        "fourier_terms": 16,
                        "channel_k": 2.0,
                        "fourier_r2": 0.99,
                        "direct_svg_to_package_ratio": 1.1,
                        "direct_svg_gzip_to_package_ratio": 1.0,
                        "source_csv_gzip_to_package_ratio": 1.0,
                    }
                ],
                "summary": {
                    "observed_break_even_samples": 1000,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = _run_precheck(
        [
            "--root",
            str(root),
            "--pattern",
            "*.json",
            "--scan-out",
            str(root / "scan.json"),
            "--contract-out",
            str(root / "contract.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["contract"]["status"] == "ok"
    assert payload["contract"]["total"] == 0
    assert payload["status_counts"]["SKIP"] == 1
    assert payload["skip_reasons"]["legacy_or_non_contract_payload"] == 1
    assert payload["skipped"] == 1
    assert payload["failed_report"] is None


def test_precheck_benchmarks_contract_out_parse_failure_still_reports_failed_report(tmp_path: Path) -> None:
    root = tmp_path / "benchmarks"
    root.mkdir()
    root.joinpath("ok.json").write_text(
        json.dumps(
            {
                "benchmark": "ok",
                "rows": [
                    {
                        "synthetic_kind": "spikes",
                        "samples": 1000,
                        "fourier_terms": 16,
                        "fourier_r2": 0.99,
                        "direct_svg_to_package_ratio": 1.1,
                        "source_csv_gzip_to_package_ratio": 1.0,
                    }
                ],
                "summary": {
                    "high_fidelity_rows_count": 1,
                    "defensible_rows_count": 0,
                    "defensible_rows_ratio": 0.0,
                    "defensible_channel_coverage_threshold": 0.9,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = _run_precheck(
        [
            "--root",
            str(root),
            "--pattern",
            "*.json",
            "--scan-out",
            str(root / "scan.json"),
            "--contract-out",
            str(root),
            "--skip-scan",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["failed_report"] == str(root)

