from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from _test_helpers import script_path as _repo_script_path


def _script_path() -> Path:
    return _repo_script_path("check_benchmark_parity.py")


def _fixture_payload() -> dict:
    return {
        "benchmark": "unit_test_benchmark",
        "parameters": {
            "sample_sizes": [100, 200],
            "synthetic_kinds": ["smooth", "noisy"],
            "fourier_terms_values": [16, 32],
            "channel_k_values": [2.0, 3.0],
            "thresholds": [0.9],
            "gate_policy": {"min_r2": 0.99, "min_channel_coverage": 0.95},
        },
        "sweep": [
            {
                "threshold": 0.9,
                "high_fidelity_rows_count": 8,
                "defensible_rows_count": 5,
                "defensible_rows_ratio": 0.625,
                "best_ratio": 2.5,
                "best_global_samples": 100,
                "best_global_sample_count": 100,
                "global_best_row": {
                    "synthetic_kind": "smooth",
                    "samples": 100,
                    "fourier_terms": 16,
                    "channel_k": 2.0,
                    "ratio": 2.5,
                },
                "benchmark_gate": {"ok": True, "errors": []},
                "rows_by_kind": {
                    "smooth": {
                        "high_fidelity_rows_count": 4,
                        "defensible_rows_count": 3,
                        "defensible_rows_ratio": 0.75,
                    },
                    "noisy": {
                        "high_fidelity_rows_count": 4,
                        "defensible_rows_count": 2,
                        "defensible_rows_ratio": 0.5,
                    },
                },
            }
        ],
    }


def test_benchmark_parity_matches_identical_payload(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    payload = _fixture_payload()
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    left.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    right.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--left",
            str(left),
            "--right",
            str(right),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "hash: MATCH" in result.stdout


def test_benchmark_parity_tolerates_metadata_only_diff(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    left_payload = _fixture_payload()
    right_payload = _fixture_payload()
    right_payload["notes"] = "metadata-only"

    left = tmp_path / "left_meta.json"
    right = tmp_path / "right_meta.json"
    left.write_text(json.dumps(left_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    right.write_text(json.dumps(right_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--left",
            str(left),
            "--right",
            str(right),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "logical_signature: PASS" in result.stdout


def test_benchmark_parity_detects_key_delta(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    left_payload = _fixture_payload()
    right_payload = _fixture_payload()
    right_payload["sweep"][0]["high_fidelity_rows_count"] = 7

    left = tmp_path / "left_delta.json"
    right = tmp_path / "right_delta.json"
    left.write_text(json.dumps(left_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    right.write_text(json.dumps(right_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--left",
            str(left),
            "--right",
            str(right),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "logical_signature: FAIL" in result.stdout
    assert "high_fidelity_rows_count" in result.stdout

