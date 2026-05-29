from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_scan_benchmark_fields_returns_rows_and_unknown_summary(tmp_path: Path) -> None:
    good = {
        "benchmark": "good",
        "rows": [
            {
                "synthetic_kind": "spikes",
                "samples": 1000,
                "fourier_terms": 16,
                "fourier_r2": 0.99,
                "direct_svg_to_package_ratio": 1.2,
                "direct_svg_gzip_to_package_ratio": 1.1,
                "source_csv_gzip_to_package_ratio": 1.0,
                "extra_field": 1,
            }
        ],
    }
    bad = {
        "benchmark": "bad",
        "rows": [
            {
                "synthetic_kind": "spikes",
                "samples": 1000,
                "fourier_terms": 16,
            }
        ],
        "sweep": [
            {
                "high_fidelity_rows_count": 3,
                "best_ratio": 1.2,
                "defensible_rows_ratio": 0.5,
            }
        ],
        "summary": {},
    }
    good_path = tmp_path / "good.json"
    bad_path = tmp_path / "bad.json"
    good_path.write_text(json.dumps(good, ensure_ascii=False, indent=2), encoding="utf-8")
    bad_path.write_text(json.dumps(bad, ensure_ascii=False, indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts" / "scan_benchmark_fields.py"),
            str(tmp_path),
            "--pattern",
            "*.json",
            "--out",
            str(tmp_path / "scan.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads((tmp_path / "scan.json").read_text(encoding="utf-8"))

    assert payload["summary"]["total"] == 2
    by_mode = payload["summary"]["mode_breakdown"]
    assert by_mode["rows"] == 1
    assert by_mode["legacy"] == 1

    bad_file = next(item for item in payload["files"] if item["path"] == str(bad_path))
    assert bad_file["rows"]["rows_missing_any_required"] == 1
    assert bad_file["sweep"]["buckets_missing_any_required"] == 1


def test_scan_benchmark_fields_excludes_contract_and_parity_reports(tmp_path: Path) -> None:
    included = tmp_path / "keep.json"
    excluded_contract = tmp_path / "terms_channel_contract.json"
    excluded_parity = tmp_path / "terms_channel_benchmark_parity_report.json"
    excluded_scan_report = tmp_path / "scan_report_ci.json"
    excluded_contract_matrix = tmp_path / "contract_matrix_ci_precheck.json"

    included.write_text(
        json.dumps(
            {
                "benchmark": "included",
                "rows": [
                    {
                        "synthetic_kind": "spikes",
                        "samples": 1000,
                        "fourier_terms": 16,
                        "fourier_r2": 0.99,
                        "direct_svg_to_package_ratio": 1.2,
                        "direct_svg_gzip_to_package_ratio": 1.1,
                        "source_csv_gzip_to_package_ratio": 1.0,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    excluded_contract.write_text(json.dumps({"benchmark": "excluded"}, ensure_ascii=False), encoding="utf-8")
    excluded_parity.write_text(json.dumps({"benchmark": "excluded"}, ensure_ascii=False), encoding="utf-8")
    excluded_scan_report.write_text(json.dumps({"status": "scan"}, ensure_ascii=False), encoding="utf-8")
    excluded_contract_matrix.write_text(json.dumps({"status": "contract"}, ensure_ascii=False), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts" / "scan_benchmark_fields.py"),
            "--root",
            str(tmp_path),
            "--out",
            str(tmp_path / "scan.json"),
            "--pattern",
            "*.json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads((tmp_path / "scan.json").read_text(encoding="utf-8"))

    assert payload["summary"]["total"] == 1
    assert payload["summary"]["mode_breakdown"]["rows"] == 1
    assert all(item["path"] != str(excluded_contract) for item in payload["files"])
    assert all(item["path"] != str(excluded_parity) for item in payload["files"])
    assert all(item["path"] != str(excluded_scan_report) for item in payload["files"])
    assert all(item["path"] != str(excluded_contract_matrix) for item in payload["files"])


def test_scan_benchmark_fields_marks_legacy_payloads(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy_hardening.json"
    legacy.write_text(
        json.dumps(
            {
                "terms": [16],
                "rows": [
                    {
                        "dataset": "steps",
                        "samples": 4000,
                        "terms": 16,
                        "raw_payload_bytes": 64000.0,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts" / "scan_benchmark_fields.py"),
            str(tmp_path),
            "--pattern",
            "*.json",
            "--out",
            str(tmp_path / "scan.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads((tmp_path / "scan.json").read_text(encoding="utf-8"))
    legacy_file = next(item for item in payload["files"] if item["path"] == str(legacy))
    assert legacy_file["mode"] == "legacy"
    assert legacy_file["errors"] == ["not_a_contract_payload: non_contract_rows_or_sweep_schema"]
