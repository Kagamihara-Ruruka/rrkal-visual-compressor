from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from vizcompress.benchmark_contracts import validate_benchmark_contract
from _test_helpers import script_path as _script_path


def _fixture_payload() -> dict:
    return {
        "benchmark": "unit_test_contract",
        "rows": [
            {
                "synthetic_kind": "smooth",
                "samples": 1000,
                "fourier_terms": 16,
                "channel_k": 3.0,
                "fourier_r2": 0.980,
                "channel_coverage_ratio": 0.96,
                "direct_svg_to_package_ratio": 1.2,
                "direct_svg_gzip_to_package_ratio": 1.1,
                "source_csv_gzip_to_package_ratio": 0.9,
            },
            {
                "synthetic_kind": "smooth",
                "samples": 1000,
                "fourier_terms": 32,
                "channel_k": 3.0,
                "fourier_r2": 0.984,
                "channel_coverage_ratio": 0.97,
                "direct_svg_to_package_ratio": 1.0,
                "direct_svg_gzip_to_package_ratio": 1.3,
                "source_csv_gzip_to_package_ratio": 1.05,
            },
        ],
        "summary": {
            "high_fidelity_rows_count": 0,
            "defensible_rows_count": 0,
            "defensible_rows_ratio": 0.0,
            "defensible_channel_coverage_threshold": 0.95,
        },
    }


def test_validate_benchmark_contract_passes_with_monotonic_terms():
    payload = _fixture_payload()
    ok, errors = validate_benchmark_contract(payload)
    assert ok is True
    assert errors == []


def test_validate_benchmark_contract_fails_on_term_regression():
    payload = _fixture_payload()
    payload["rows"][1]["fourier_r2"] = 0.5
    ok, errors = validate_benchmark_contract(payload)
    assert ok is False
    assert any("decreased" in item for item in errors)


def test_validate_benchmark_contract_checks_term_regression_without_channel_k():
    payload = {
        "benchmark": "unit_test_no_channel_regression",
        "rows": [
            {
                "synthetic_kind": "spikes",
                "samples": 1024,
                "fourier_terms": 16,
                "fourier_r2": 0.96,
                "direct_svg_to_package_ratio": 1.5,
                "direct_svg_gzip_to_package_ratio": 1.2,
                "source_csv_gzip_to_package_ratio": 1.1,
            },
            {
                "synthetic_kind": "spikes",
                "samples": 1024,
                "fourier_terms": 32,
                "fourier_r2": 0.90,
                "direct_svg_to_package_ratio": 1.4,
                "direct_svg_gzip_to_package_ratio": 1.1,
                "source_csv_gzip_to_package_ratio": 1.05,
            },
        ],
    }
    ok, errors = validate_benchmark_contract(payload)
    assert ok is False
    assert any("decreased" in item for item in errors)


def test_validate_benchmark_contract_fails_on_bad_coverage_or_ratio():
    payload = _fixture_payload()
    payload["rows"][0]["channel_coverage_ratio"] = 1.4
    ok, errors = validate_benchmark_contract(payload)
    assert ok is False
    assert any("outside [0,1]" in item for item in errors)


def test_validate_benchmark_contract_handles_rows_without_channel_k():
    payload = {
        "benchmark": "unit_test_no_channel",
        "rows": [
            {
                "synthetic_kind": "spikes",
                "samples": 1000,
                "fourier_terms": 32,
                "fourier_r2": 0.98,
                "direct_svg_to_package_ratio": 2.0,
                "direct_svg_gzip_to_package_ratio": 1.4,
                "source_csv_gzip_to_package_ratio": 1.2,
                "source_csv_to_package_ratio": 1.1,
            }
        ],
        "summary": {
            "high_fidelity_rows_count": 0,
            "defensible_rows_count": 0,
            "defensible_rows_ratio": 0.0,
            "defensible_channel_coverage_threshold": 0.9,
        },
    }
    ok, errors = validate_benchmark_contract(payload)
    assert ok is True
    assert errors == []


def test_validate_benchmark_contract_rejects_non_finite_channel_k():
    payload = {
        "benchmark": "unit_test_non_finite",
        "rows": [
            {
                "synthetic_kind": "spikes",
                "samples": 1000,
                "fourier_terms": 32,
                "fourier_r2": 0.98,
                "channel_k": float("inf"),
                "direct_svg_to_package_ratio": 1.0,
                "direct_svg_gzip_to_package_ratio": 1.1,
                "source_csv_gzip_to_package_ratio": 1.2,
            }
        ],
    }
    ok, errors = validate_benchmark_contract(payload)
    assert ok is False
    assert any("channel_k" in err for err in errors)


def test_validate_benchmark_contract_rejects_invalid_samples_and_terms():
    payload = {
        "benchmark": "unit_test_invalid_shape",
        "rows": [
            {
                "synthetic_kind": "spikes",
                "samples": -10,
                "fourier_terms": 16.0,
                "fourier_r2": 0.98,
                "direct_svg_to_package_ratio": 1.0,
                "direct_svg_gzip_to_package_ratio": 1.0,
                "source_csv_gzip_to_package_ratio": 1.0,
                "source_csv_to_package_ratio": -1.0,
            },
            {
                "synthetic_kind": "spikes",
                "samples": 1000,
                "fourier_terms": 0,
                "fourier_r2": 0.99,
                "direct_svg_to_package_ratio": 1.0,
                "direct_svg_gzip_to_package_ratio": 1.0,
                "source_csv_gzip_to_package_ratio": 1.0,
            },
        ],
    }
    ok, errors = validate_benchmark_contract(payload)
    assert ok is False
    assert any("samples must be a positive integer" in err for err in errors)
    assert any("fourier_terms must be a positive integer" in err for err in errors)
    assert any("source_csv_to_package_ratio" in err for err in errors)


def test_validate_benchmark_contract_rejects_invalid_summary_values():
    payload = {
        "benchmark": "unit_test_invalid_summary",
        "rows": [
            {
                "synthetic_kind": "spikes",
                "samples": 1000,
                "fourier_terms": 16,
                "fourier_r2": 0.995,
                "channel_coverage_ratio": 0.93,
                "direct_svg_to_package_ratio": 1.0,
                "direct_svg_gzip_to_package_ratio": 1.0,
                "source_csv_gzip_to_package_ratio": 1.0,
            }
        ],
        "summary": {
            "high_fidelity_rows_count": "one",
            "defensible_rows_count": -1,
            "defensible_rows_ratio": 2.0,
            "defensible_channel_coverage_threshold": 1.5,
        },
    }
    ok, errors = validate_benchmark_contract(payload)
    assert ok is False
    assert any("high_fidelity_rows_count invalid" in err for err in errors)
    assert any("defensible_rows_count invalid" in err for err in errors)
    assert any("defensible_rows_ratio invalid" in err for err in errors)
    assert any("summary.defensible_channel_coverage_threshold invalid" in err for err in errors)


def test_validate_benchmark_contract_rejects_invalid_channel_coverage():
    payload = {
        "benchmark": "unit_test_invalid_coverage",
        "rows": [
            {
                "synthetic_kind": "spikes",
                "samples": 1000,
                "fourier_terms": 16,
                "fourier_r2": 0.995,
                "channel_coverage_ratio": float("nan"),
                "direct_svg_to_package_ratio": 1.0,
                "direct_svg_gzip_to_package_ratio": 1.0,
                "source_csv_gzip_to_package_ratio": 1.0,
            }
        ],
    }
    ok, errors = validate_benchmark_contract(payload)
    assert ok is False
    assert any("channel_coverage_ratio" in err for err in errors)


def test_validate_benchmark_contract_rejects_boolean_metrics():
    payload = {
        "benchmark": "unit_test_boolean_metric",
        "rows": [
            {
                "synthetic_kind": "spikes",
                "samples": True,
                "fourier_terms": 16,
                "fourier_r2": 0.995,
                "direct_svg_to_package_ratio": 1.1,
                "direct_svg_gzip_to_package_ratio": 1.0,
                "source_csv_gzip_to_package_ratio": 1.0,
            }
        ],
    }
    ok, errors = validate_benchmark_contract(payload)
    assert ok is False
    assert any("samples must be a positive integer" in err for err in errors)


def test_validate_benchmark_contract_rejects_boolean_fourier_r2():
    payload = {
        "benchmark": "unit_test_boolean_r2",
        "rows": [
            {
                "synthetic_kind": "spikes",
                "samples": 1000,
                "fourier_terms": 16,
                "fourier_r2": False,
                "direct_svg_to_package_ratio": 1.0,
                "direct_svg_gzip_to_package_ratio": 1.0,
                "source_csv_gzip_to_package_ratio": 1.0,
            }
        ],
    }
    ok, errors = validate_benchmark_contract(payload)
    assert ok is False
    assert any("fourier_r2 missing or invalid" in err for err in errors)


def test_validate_benchmark_contract_rejects_boolean_ratio_fields():
    payload = {
        "benchmark": "unit_test_boolean_ratio",
        "rows": [
            {
                "synthetic_kind": "spikes",
                "samples": 1000,
                "fourier_terms": 16,
                "fourier_r2": 0.995,
                "direct_svg_to_package_ratio": False,
                "direct_svg_gzip_to_package_ratio": 1.0,
                "source_csv_gzip_to_package_ratio": 1.0,
            }
        ],
    }
    ok, errors = validate_benchmark_contract(payload)
    assert ok is False
    assert any("direct_svg_to_package_ratio" in err for err in errors)


def test_validate_benchmark_contract_allows_missing_summary():
    payload = {
        "benchmark": "unit_test_missing_summary",
        "rows": [
            {
                "synthetic_kind": "spikes",
                "samples": 1000,
                "fourier_terms": 16,
                "fourier_r2": 0.995,
                "channel_coverage_ratio": 0.98,
                "direct_svg_to_package_ratio": 1.1,
                "direct_svg_gzip_to_package_ratio": 1.0,
                "source_csv_gzip_to_package_ratio": 1.0,
            }
        ],
    }
    ok, errors = validate_benchmark_contract(payload)
    assert ok is True
    assert errors == []


def test_validate_benchmark_contract_script(tmp_path: Path):
    payload = _fixture_payload()
    in_json = tmp_path / "bench.json"
    report = tmp_path / "contract.json"
    in_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path("validate_benchmark_contracts.py")),
            str(in_json),
            "--out",
            str(report),
            "--tolerance",
            "1e-12",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0"
    assert data["input"] == str(in_json)
    assert data["passed"] is True
    assert data["error_count"] == 0


def test_validate_benchmark_contract_script_reports_field_path(tmp_path: Path):
    payload = {
        "benchmark": "unit_test_cli_output_path",
        "rows": [
            {
                "synthetic_kind": "spikes",
                "samples": 1000,
                "fourier_terms": 16,
                "fourier_r2": 0.995,
                "direct_svg_to_package_ratio": -1.0,
                "direct_svg_gzip_to_package_ratio": 1.0,
                "source_csv_gzip_to_package_ratio": 1.0,
            }
        ],
    }
    in_json = tmp_path / "bench.json"
    in_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path("validate_benchmark_contracts.py")),
            str(in_json),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "FAIL" in result.stdout
    assert (
        "row[0].direct_svg_to_package_ratio" in result.stdout
        or "row[0].direct_svg_gzip_to_package_ratio" in result.stdout
    )


def test_validate_benchmark_contract_script_rejects_malformed_payload(tmp_path: Path) -> None:
    in_json = tmp_path / "bench_invalid.json"
    in_json.write_bytes(b"\xff\x00\xffbad json")

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path("validate_benchmark_contracts.py")),
            str(in_json),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "unable to read benchmark payload" in (result.stdout + result.stderr)


def test_validate_benchmark_contract_reports_sweep_field_path():
    payload = {
        "benchmark": "unit_test_sweep_field_path",
        "sweep": [
            {
                "high_fidelity_rows_count": "bad",
                "defensible_rows_count": 0,
                "defensible_rows_ratio": 0.0,
                "best_ratio": 1.0,
            }
        ],
    }
    ok, errors = validate_benchmark_contract(payload)
    assert ok is False
    assert any("sweep[0].high_fidelity_rows_count" in err for err in errors)


def test_validate_benchmark_contract_reports_invalid_sweep_ratio_values():
    payload = {
        "benchmark": "unit_test_invalid_sweep_ratio",
        "sweep": [
            {
                "high_fidelity_rows_count": 10,
                "defensible_rows_count": 5,
                "defensible_rows_ratio": 0.5,
                "best_ratio": "not-a-number",
                "best_defensible_ratio": float("inf"),
            }
        ],
    }
    ok, errors = validate_benchmark_contract(payload)
    assert ok is False
    assert any("best_ratio" in err for err in errors)
    assert any("best_defensible_ratio" in err for err in errors)


def test_validate_benchmark_contract_reports_invalid_sweep_counts_with_bool():
    payload = {
        "benchmark": "unit_test_invalid_sweep_counts_bool",
        "sweep": [
            {
                "high_fidelity_rows_count": True,
                "defensible_rows_count": False,
                "defensible_rows_ratio": 0.5,
                "best_ratio": 0.0,
            }
        ],
    }
    ok, errors = validate_benchmark_contract(payload)
    assert ok is False
    assert any("high_fidelity_rows_count" in err for err in errors)
    assert any("defensible_rows_count" in err for err in errors)


def test_validate_benchmark_contracts_all_script(tmp_path: Path):
    bad = tmp_path / "bad.json"
    good = tmp_path / "good.json"
    good.write_text(
        json.dumps(
            {
                "benchmark": "unit_rows",
                "rows": [
                    {
                        "synthetic_kind": "smooth",
                        "samples": 1000,
                        "fourier_terms": 16,
                        "channel_k": 3.0,
                        "fourier_r2": 0.99,
                        "direct_svg_to_package_ratio": 1.2,
                        "direct_svg_gzip_to_package_ratio": 1.2,
                        "source_csv_gzip_to_package_ratio": 1.2,
                    },
                    {
                        "synthetic_kind": "smooth",
                        "samples": 1000,
                        "fourier_terms": 32,
                        "channel_k": 3.0,
                        "fourier_r2": 0.991,
                        "direct_svg_to_package_ratio": 1.2,
                        "direct_svg_gzip_to_package_ratio": 1.2,
                        "source_csv_gzip_to_package_ratio": 1.2,
                    },
                ],
                "summary": {
                    "high_fidelity_rows_count": 2,
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
    bad.write_text(
        json.dumps(
            {
                "benchmark": "unit_rows",
                "rows": [
                    {
                        "synthetic_kind": "smooth",
                        "samples": 1000,
                        "fourier_terms": 16,
                        "channel_k": 3.0,
                        "fourier_r2": 0.99,
                        "direct_svg_to_package_ratio": 1.2,
                        "direct_svg_gzip_to_package_ratio": -1.0,
                        "source_csv_gzip_to_package_ratio": 1.2,
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

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path("validate_benchmark_contracts_all.py")),
            "--root",
            str(tmp_path),
            "--out",
            str(tmp_path / "all_contracts.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    report = json.loads((tmp_path / "all_contracts.json").read_text(encoding="utf-8"))
    assert report["schema_version"] == "1.0"
    assert report["total_inputs"] == 2
    assert report["total"] == 2
    assert report["failed"] == 1
    assert "FAIL" in result.stdout
    assert "failed=1" in result.stdout
    assert "status_counts" in report
    assert report["status_counts"]["PASS"] == 1
    assert report["status_counts"]["FAIL"] == 1


def test_validate_benchmark_contracts_all_script_skips_legacy_row_payload_without_summary_counters(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy_rows.json"
    contract = tmp_path / "contract.json"
    legacy.write_text(
        json.dumps(
            {
                "benchmark": "legacy_rows_only",
                "rows": [
                    {
                        "synthetic_kind": "spikes",
                        "samples": 1000,
                        "fourier_terms": 16,
                        "channel_k": 3.0,
                        "fourier_r2": 0.99,
                        "direct_svg_to_package_ratio": 1.1,
                        "source_csv_gzip_to_package_ratio": 1.0,
                        "direct_svg_gzip_to_package_ratio": 1.0,
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
    contract.write_text(
        json.dumps(
            {
                "benchmark": "contract_rows",
                "rows": [
                    {
                        "synthetic_kind": "spikes",
                        "samples": 1000,
                        "fourier_terms": 16,
                        "channel_k": 3.0,
                        "fourier_r2": 0.99,
                        "direct_svg_to_package_ratio": 1.1,
                        "source_csv_gzip_to_package_ratio": 1.0,
                        "direct_svg_gzip_to_package_ratio": 1.0,
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

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path("validate_benchmark_contracts_all.py")),
            "--root",
            str(tmp_path),
            "--out",
            str(tmp_path / "all_contracts_legacy.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    report = json.loads((tmp_path / "all_contracts_legacy.json").read_text(encoding="utf-8"))
    assert report["schema_version"] == "1.0"
    assert report["total_inputs"] == 2
    assert report["total"] == 1
    assert report["failed"] == 0
    assert report["skipped"] == 1
    assert report["status_counts"]["SKIP"] == 1
    assert report["status_counts"]["PASS"] == 1
    legacy_row = next(row for row in report["rows"] if row["input"] == str(legacy))
    assert legacy_row["status"] == "SKIP"
    assert legacy_row["skip_reason"] == "legacy_or_non_contract_payload"


def test_validate_benchmark_contracts_all_script_ignores_generated_report_names(tmp_path: Path) -> None:
    good = tmp_path / "good.json"
    legacy = tmp_path / "legacy_rows.json"
    scan = tmp_path / "scan_report.json"
    matrix = tmp_path / "contract_matrix_precheck.json"

    good.write_text(
        json.dumps(
            {
                "benchmark": "contract_rows",
                "rows": [
                    {
                        "synthetic_kind": "spikes",
                        "samples": 1024,
                        "fourier_terms": 16,
                        "channel_k": 3.0,
                        "fourier_r2": 0.99,
                        "direct_svg_to_package_ratio": 1.1,
                        "source_csv_gzip_to_package_ratio": 1.0,
                        "direct_svg_gzip_to_package_ratio": 1.0,
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
    legacy.write_text(
        json.dumps(
            {
                "benchmark": "legacy_rows",
                "rows": [
                    {
                        "synthetic_kind": "spikes",
                        "samples": 1024,
                        "fourier_terms": 16,
                        "channel_k": 3.0,
                        "fourier_r2": 0.99,
                        "direct_svg_to_package_ratio": 1.1,
                        "source_csv_gzip_to_package_ratio": 1.0,
                        "direct_svg_gzip_to_package_ratio": 1.0,
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
    scan.write_text("{}", encoding="utf-8")
    matrix.write_text("{}", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path("validate_benchmark_contracts_all.py")),
            "--root",
            str(tmp_path),
            "--out",
            str(tmp_path / "all_contracts_ignore_generated.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    report = json.loads((tmp_path / "all_contracts_ignore_generated.json").read_text(encoding="utf-8"))
    assert report["schema_version"] == "1.0"
    assert report["total_inputs"] == 2
    assert report["total"] == 1
    assert report["failed"] == 0
    assert report["skipped"] == 1
    observed_inputs = {row["input"] for row in report["rows"]}
    assert str(scan) not in observed_inputs
    assert str(matrix) not in observed_inputs


def test_validate_benchmark_contracts_all_script_reports_sweep_path(tmp_path: Path):
    bad = tmp_path / "bad.json"
    good = tmp_path / "good.json"
    good.write_text(
        json.dumps(
            {
                "benchmark": "unit_rows_all_good",
                "rows": [
                    {
                        "synthetic_kind": "smooth",
                        "samples": 1000,
                        "fourier_terms": 16,
                        "channel_k": 3.0,
                        "fourier_r2": 0.99,
                        "direct_svg_to_package_ratio": 1.2,
                        "direct_svg_gzip_to_package_ratio": 1.2,
                        "source_csv_gzip_to_package_ratio": 1.2,
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
    bad.write_text(
        json.dumps(
            {
                "benchmark": "unit_rows_all_bad_sweep",
                "sweep": [
                    {
                        "high_fidelity_rows_count": "bad",
                        "defensible_rows_count": 0,
                        "defensible_rows_ratio": 0.0,
                        "best_ratio": 1.0,
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

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path("validate_benchmark_contracts_all.py")),
            "--root",
            str(tmp_path),
            "--out",
            str(tmp_path / "all_contracts_sweep.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    report = json.loads((tmp_path / "all_contracts_sweep.json").read_text(encoding="utf-8"))
    assert report["total"] == 2
    assert report["failed"] == 1
    assert "sweep[0].high_fidelity_rows_count" in result.stdout
    assert any("sweep[0].high_fidelity_rows_count" in err for row in report["rows"] for err in row["errors"])


def test_validate_benchmark_contracts_all_script_skips_non_benchmark_payload(tmp_path: Path) -> None:
    bench = tmp_path / "good.json"
    non_benchmark = tmp_path / "notes.json"
    bench.write_text(
        json.dumps(
            {
                "benchmark": "rows_only",
                "rows": [
                    {
                        "synthetic_kind": "smooth",
                        "samples": 1000,
                        "fourier_terms": 16,
                        "channel_k": 3.0,
                        "fourier_r2": 0.99,
                        "direct_svg_to_package_ratio": 1.2,
                        "direct_svg_gzip_to_package_ratio": 1.1,
                        "source_csv_gzip_to_package_ratio": 1.0,
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
    non_benchmark.write_text(
        json.dumps(
            {
                "note": "legacy summary",
                "status": "manual_aggregation",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path("validate_benchmark_contracts_all.py")),
            "--root",
            str(tmp_path),
            "--out",
            str(tmp_path / "all_contracts_skip.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    report = json.loads((tmp_path / "all_contracts_skip.json").read_text(encoding="utf-8"))
    assert report["total_inputs"] == 2
    assert report["skipped"] == 1
    assert report["status_counts"]["PASS"] == 1
    assert report["status_counts"]["SKIP"] == 1


