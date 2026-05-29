from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _legacy_report(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "dataset": "spikes",
                        "samples": 1024,
                        "terms": 16,
                        "global": {
                            "r2": 0.991,
                            "payload_ratio": 2.0,
                            "leakage_ratio": 0.2,
                        },
                        "gates": {"defensible": True},
                    },
                    {
                        "dataset": "spikes",
                        "samples": 1024,
                        "terms": 64,
                        "global": {
                            "r2": 0.995,
                            "payload_ratio": 1.8,
                            "leakage_ratio": 0.15,
                        },
                        "gates": {"defensible": False},
                    },
                    {
                        "dataset": "spikes",
                        "samples": 1024,
                        "terms": "bad",
                        "global": {"r2": 0.6},
                    },
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _run_convert(args: list[str]) -> subprocess.CompletedProcess:
    script = Path(__file__).resolve().parents[1] / "scripts" / "convert_legacy_hardening_reports.py"
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_convert_legacy_hardening_reports_dry_run_outputs_counts(tmp_path: Path) -> None:
    source = tmp_path / "defensible_hardening_report.json"
    _legacy_report(source)

    result = _run_convert([
        "--root",
        str(tmp_path),
        "--dry-run",
    ])

    assert result.returncode == 0
    payload = json.loads(result.stdout.strip())
    assert payload["count"] == 1
    assert payload["files"][0]["source"] == str(source)
    assert payload["files"][0]["output_rows"] == 2


def test_convert_legacy_hardening_reports_writes_contract_json(tmp_path: Path) -> None:
    source = tmp_path / "defensible_hardening_report_any.json"
    _legacy_report(source)

    result = _run_convert([
        str(source),
    ])
    assert result.returncode == 0

    output = tmp_path / "defensible_hardening_report_any_contract.json"
    assert output.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["benchmark"] == "legacy_hardening_contract_any"
    assert payload["converted_from"] == "legacy_hardening_report"
    assert payload["source_file"] == str(source)
    assert payload["summary"]["high_fidelity_rows_count"] == 2
    assert payload["summary"]["defensible_rows_count"] == 1
    assert payload["rows"][0]["_legacy_source"] is True
    assert payload["rows"][0]["synthetic_kind"] == "spikes"
    assert payload["rows"][1]["_legacy_source"] is True
    assert payload["rows"][0]["fourier_terms"] == 16
    assert payload["rows"][1]["fourier_terms"] == 64


def test_convert_legacy_hardening_reports_no_input(tmp_path: Path) -> None:
    result = _run_convert([
        "--root",
        str(tmp_path),
    ])
    assert result.returncode == 1
    assert "no legacy files found" in result.stdout
