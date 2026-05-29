from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


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

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts" / "precheck_benchmarks.py"),
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

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts" / "precheck_benchmarks.py"),
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
    assert payload["status_counts"]["PASS"] == 1
    assert payload["status_counts"].get("SKIP", 0) == 0
    assert payload["skipped"] == 0
    assert payload["total_inputs"] == 1


def test_precheck_benchmarks_help_includes_benefit_flags() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts" / "precheck_benchmarks.py"),
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
