from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _payload(valid: bool = True) -> dict:
    payload = {
        "rows": [
            {
                "synthetic_kind": "smooth",
                "samples": 1000,
                "fourier_terms": 16,
                "channel_k": 3.0,
                "fourier_r2": 0.99,
                "channel_coverage_ratio": 0.95,
                "direct_svg_to_package_ratio": 1.2,
                "direct_svg_gzip_to_package_ratio": 1.2,
                "source_csv_gzip_to_package_ratio": 1.2,
            },
            {
                "synthetic_kind": "smooth",
                "samples": 1000,
                "fourier_terms": 32,
                "channel_k": 3.0,
                "fourier_r2": 0.995,
                "channel_coverage_ratio": 0.96,
                "direct_svg_to_package_ratio": 1.1,
                "direct_svg_gzip_to_package_ratio": 1.1,
                "source_csv_gzip_to_package_ratio": 1.1,
            },
        ],
        "summary": {
            "high_fidelity_rows_count": 2,
            "defensible_rows_count": 2,
            "defensible_rows_ratio": 1.0,
            "defensible_channel_coverage_threshold": 0.9,
        },
    }

    if not valid:
        payload["rows"][1]["direct_svg_gzip_to_package_ratio"] = -1.0
    return payload


def test_compare_terms_channel_parity_with_contract_checks(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]

    left_payload = _payload(True)
    right_payload = _payload(True)

    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    report = tmp_path / "report.json"

    left.write_text(json.dumps(left_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    right.write_text(json.dumps(right_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "compare_terms_channel_benchmark_parity.py"),
            "--left-root",
            str(tmp_path),
            "--right-root",
            str(tmp_path),
            "--left-out-json",
            left.name,
            "--right-out-json",
            right.name,
            "--report-json",
            str(report),
            "--skip-run",
            "--validate-contract",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert report.exists()
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["contract_validation"]["enabled"] is True
    assert payload["contract_validation"]["both_passed"] is True
    assert payload["parity_ok"] is True


def test_compare_terms_channel_parity_contract_failure(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]

    left_payload = _payload(True)
    right_payload = _payload(False)

    left = tmp_path / "left_invalid.json"
    right = tmp_path / "right_invalid.json"
    report = tmp_path / "report_invalid.json"

    left.write_text(json.dumps(left_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    right.write_text(json.dumps(right_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "compare_terms_channel_benchmark_parity.py"),
            "--left-root",
            str(tmp_path),
            "--right-root",
            str(tmp_path),
            "--left-out-json",
            left.name,
            "--right-out-json",
            right.name,
            "--report-json",
            str(report),
            "--skip-run",
            "--validate-contract",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    text = result.stdout + result.stderr
    assert "contract validation failed" in text
    assert not report.exists()
