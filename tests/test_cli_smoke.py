from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import sys
import subprocess
from _test_helpers import run_cli as _run_cli_impl

from vizcompress.benchmark_contracts import validate_benchmark_contract
from vizcompress.cli import PackageConfig


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "vizcompress.cli", *args]
    return _run_cli_impl(cmd, capture_output=True, text=True, check=False)

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


def test_package_config_type_allows_reconstruct_options():
    config = PackageConfig(package=Path("demo.vizasset"))
    assert config.package == Path("demo.vizasset")
    assert config.samples == 1200
    assert config.include_channel is True
    assert config.include_sparse_residual is True
    assert config.include_noise_layer is True
    assert config.include_retained is True


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


def test_reconstruct_command_supports_signal_and_sample_overrides(tmp_path: Path) -> None:
    out_dir = tmp_path / "reconstruct_smoke"
    package_name = "model.vizretain"
    package_dir = out_dir / package_name

    _run_cli(
        "build",
        "--synthetic",
        "128",
        "--synthetic-kind",
        "spikes",
        "--fourier-terms",
        "16",
        "--package",
        "--out",
        str(out_dir),
        "--package-name",
        package_name,
        "--channel",
    )

    center = _parse_json_stdout(_run_cli("reconstruct", str(package_dir)))
    assert center["reconstructed"]["samples"] == 1200
    assert center["reconstructed"]["y_max"] >= center["reconstructed"]["y_min"]

    retained = _parse_json_stdout(_run_cli("reconstruct", str(package_dir), "--signal", "retained", "--samples", "64"))
    assert retained["reconstructed"]["samples"] == 64
    assert retained["reconstructed"]["y_max"] >= retained["reconstructed"]["y_min"]
