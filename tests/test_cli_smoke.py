from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from vizcompress.benchmark_contracts import validate_benchmark_contract


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    root = Path(__file__).resolve().parents[1]
    cmd = [sys.executable, "-m", "vizcompress.cli", *args]
    result = subprocess.run(
        cmd,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "CLI command failed"
            f"\ncmd: {' '.join(cmd)}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result


def test_bench_command_writes_contract_json_and_markdown(tmp_path: Path) -> None:
    out_json = tmp_path / "bench.json"
    out_md = tmp_path / "bench.md"
    _run_cli(
        "bench",
        "--synthetic-sizes",
        "100",
        "--synthetic-kind",
        "spikes",
        "--fourier-terms",
        "16",
        "--svg-samples",
        "120",
        "--out",
        str(out_json),
        "--report-md",
        str(out_md),
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    ok, errors = validate_benchmark_contract(payload)
    assert ok is True
    assert errors == []
    assert isinstance(payload.get("rows"), list) and len(payload["rows"]) == 1
    assert out_md.exists()


def _parse_json_stdout(result: subprocess.CompletedProcess) -> dict[str, Any]:
    return json.loads(result.stdout)


def test_build_inspect_and_verify_cycle(tmp_path: Path) -> None:
    out_dir = tmp_path / "build_smoke"
    package_name = "model.vizretain"
    out_pkg = out_dir / package_name
    build_result = _run_cli(
        "build",
        "--synthetic",
        "128",
        "--synthetic-kind",
        "spikes",
        "--fourier-terms",
        "16",
        "--svg-samples",
        "120",
        "--channel",
        "--package",
        "--out",
        str(out_dir),
        "--package-name",
        package_name,
    )
    build_summary: dict[str, Any] = _parse_json_stdout(build_result)
    assert Path(build_summary["outputs"][0]).parent.exists()
    assert (out_pkg / "asset.json").exists()

    inspect_result = _run_cli("inspect", str(out_pkg), "--samples", "64")
    inspect_payload = _parse_json_stdout(inspect_result)
    assert inspect_payload["package"] == str(out_pkg)
    assert inspect_payload["asset_type"] == "rrkal.visual_compressor.timeseries"
    assert inspect_payload["contains_noise_layer"] in (True, False)

    verify_result = _run_cli("verify", str(out_pkg), "--samples", "64", "--synthetic", "128", "--synthetic-kind", "spikes")
    verify_payload = _parse_json_stdout(verify_result)
    assert verify_payload["ok"] is True
    assert verify_payload["errors"] == []


def test_compare_command_reports_baseline_evidence(tmp_path: Path) -> None:
    out_dir = tmp_path / "compare_smoke"
    package_name = "model.vizretain"
    package_dir = out_dir / package_name
    baseline_svg = out_dir / "direct.svg"

    _run_cli(
        "build",
        "--synthetic",
        "96",
        "--synthetic-kind",
        "spikes",
        "--fourier-terms",
        "16",
        "--svg-samples",
        "120",
        "--channel",
        "--direct-svg",
        "--package",
        "--out",
        str(out_dir),
        "--package-name",
        package_name,
    )
    assert baseline_svg.exists()
    assert package_dir.exists()

    compare_result = _run_cli(
        "compare",
        str(package_dir),
        "--baseline",
        f"direct={baseline_svg}",
    )
    compare_payload = _parse_json_stdout(compare_result)
    assert compare_payload["package"] == str(package_dir)
    assert "baseline_evidence" in compare_payload
    assert "direct" in compare_payload["baseline_evidence"]
    direct_evidence = compare_payload["baseline_evidence"]["direct"]
    assert direct_evidence["present"] is True
    assert direct_evidence["bytes"] > 0
