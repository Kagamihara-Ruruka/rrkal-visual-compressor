from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from vizcompress.benchmark_contracts import validate_benchmark_contract


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


def test_validate_benchmark_contract_fails_on_bad_coverage_or_ratio():
    payload = _fixture_payload()
    payload["rows"][0]["channel_coverage_ratio"] = 1.4
    ok, errors = validate_benchmark_contract(payload)
    assert ok is False
    assert any("outside [0,1]" in item for item in errors)


def test_validate_benchmark_contract_script(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    payload = _fixture_payload()
    in_json = tmp_path / "bench.json"
    report = tmp_path / "contract.json"
    in_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "validate_benchmark_contracts.py"),
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
    assert data["input"] == str(in_json)
    assert data["passed"] is True
    assert data["error_count"] == 0

