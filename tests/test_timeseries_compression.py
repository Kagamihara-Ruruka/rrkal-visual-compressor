from __future__ import annotations

import json
import subprocess
import sys

import numpy as np

from vizcompress.analyzers import analyze_time_series
from vizcompress.benchmarks import benchmark_synthetic_sizes, parse_sample_sizes
from vizcompress.compressors import compress_fourier, compress_fourier_channel, compress_rdp
from vizcompress.core import CompressionReport
from vizcompress.data import make_synthetic_signal, read_csv_timeseries
from vizcompress.exporters import write_channel_svg, write_demo, write_fourier_svg, write_metrics, write_rdp_svg
from vizcompress.packages import load_vizasset_manifest, reconstruct_channel, reconstruct_fourier, write_vizasset


def test_rdp_and_fourier_compress_synthetic_series():
    series = make_synthetic_signal(20_000)

    rdp = compress_rdp(series, epsilon=0.012)
    fourier = compress_fourier(series, terms=96)

    assert 2 < rdp.parameter_count < series.sample_count
    assert fourier.parameter_count == 96
    assert rdp.metrics["r2"] > 0.9
    assert fourier.metrics["r2"] > 0.99


def test_analyze_time_series_reports_domain_profile():
    series = make_synthetic_signal(1000)

    profile = analyze_time_series(series)

    assert profile.sample_count == 1000
    assert profile.x_uniform is True
    assert profile.nonfinite_count == 0
    assert profile.x_min == 0.0
    assert profile.x_max == 1.0
    assert profile.y_min < profile.y_max


def test_fourier_channel_models_center_and_residual_band():
    series = make_synthetic_signal(20_000)

    channel = compress_fourier_channel(series, terms=64, window=501, k=3.0, band_epsilon=0.01)

    assert channel.center.parameter_count == 64
    assert 0 < len(channel.band_indices) < series.sample_count
    assert channel.parameter_count == 64 + len(channel.band_indices)
    assert channel.coverage_ratio > 0.94
    assert channel.metrics["mean_band_width"] > 0.0


def test_exporters_write_expected_files(tmp_path):
    series = make_synthetic_signal(10_000)
    rdp = compress_rdp(series, epsilon=0.012)
    fourier = compress_fourier(series, terms=64)
    channel = compress_fourier_channel(series, terms=64, window=401, k=3.0, band_epsilon=0.01)
    report = CompressionReport(input_samples=series.sample_count, rdp=rdp, fourier=fourier, channel=channel)

    rdp_svg = write_rdp_svg(tmp_path / "rdp.svg", series, rdp)
    fourier_svg = write_fourier_svg(tmp_path / "fourier.svg", series, fourier, samples=800)
    channel_svg = write_channel_svg(tmp_path / "channel.svg", series, channel, samples=800)
    demo = write_demo(tmp_path / "demo.py", series.sample_count, terms=64)
    metrics = write_metrics(
        tmp_path / "metrics.json",
        report,
        [rdp_svg.name, fourier_svg.name, channel_svg.name, demo.name],
    )

    assert rdp_svg.read_text(encoding="utf-8").startswith("<svg")
    assert "Fourier" in fourier_svg.read_text(encoding="utf-8")
    assert "Fourier channel model" in channel_svg.read_text(encoding="utf-8")
    assert "FOURIER_TERMS = 64" in demo.read_text(encoding="utf-8")
    data = json.loads(metrics.read_text(encoding="utf-8"))
    assert data["input"]["samples"] == 10_000
    assert data["fourier"]["kept_coefficients"] == 64
    assert data["channel"]["coverage_ratio"] > 0.94


def test_write_vizasset_package(tmp_path):
    series = make_synthetic_signal(10_000)
    rdp = compress_rdp(series, epsilon=0.012)
    fourier = compress_fourier(series, terms=64)
    channel = compress_fourier_channel(series, terms=64, window=401, k=3.0, band_epsilon=0.01)
    report = CompressionReport(input_samples=series.sample_count, rdp=rdp, fourier=fourier, channel=channel)
    preview = write_channel_svg(tmp_path / "preview_source.svg", series, channel, samples=800)
    demo = write_demo(tmp_path / "demo_source.py", series.sample_count, terms=64)
    metrics = write_metrics(tmp_path / "metrics_source.json", report, ["preview_source.svg", "demo_source.py"])

    package = write_vizasset(
        tmp_path / "model.vizasset",
        series=series,
        report=report,
        preview_svg=preview,
        metrics_json=metrics,
        demo_py=demo,
    )

    manifest = load_vizasset_manifest(package)
    assert manifest["asset_type"] == "rrkal.visual_compressor.timeseries"
    assert manifest["model"]["primary_method"] == "fourier_channel"
    assert manifest["source"]["profile"]["x_uniform"] is True
    assert manifest["files"]["model"]["path"] == "model.npz"
    assert len(manifest["files"]["preview"]["sha256"]) == 64
    assert (package / "asset.json").exists()
    assert (package / "model.npz").exists()
    assert (package / "preview.svg").exists()


def test_vizasset_reconstructs_fourier_and_channel(tmp_path):
    series = make_synthetic_signal(5000)
    rdp = compress_rdp(series, epsilon=0.012)
    fourier = compress_fourier(series, terms=48)
    channel = compress_fourier_channel(series, terms=48, window=301, k=3.0, band_epsilon=0.01)
    report = CompressionReport(input_samples=series.sample_count, rdp=rdp, fourier=fourier, channel=channel)
    preview = write_channel_svg(tmp_path / "preview_source.svg", series, channel, samples=500)
    demo = write_demo(tmp_path / "demo_source.py", series.sample_count, terms=48)
    metrics = write_metrics(tmp_path / "metrics_source.json", report, ["preview_source.svg", "demo_source.py"])
    package = write_vizasset(
        tmp_path / "model.vizasset",
        series=series,
        report=report,
        preview_svg=preview,
        metrics_json=metrics,
        demo_py=demo,
    )

    reconstructed = reconstruct_fourier(package, samples=500)
    channel_reconstructed = reconstruct_channel(package, samples=500)

    assert reconstructed.sample_count == 500
    assert channel_reconstructed["x"].shape == (500,)
    assert np.all(channel_reconstructed["upper_y"] >= channel_reconstructed["center_y"])
    assert np.all(channel_reconstructed["lower_y"] <= channel_reconstructed["center_y"])


def test_benchmark_reports_size_sweep():
    result = benchmark_synthetic_sizes(
        [1000, 5000],
        fourier_terms=32,
        rdp_epsilon=0.012,
        svg_samples=300,
        channel=True,
        channel_k=3.0,
        channel_window=201,
        channel_band_epsilon=0.01,
    )

    assert parse_sample_sizes("1000,5000") == [1000, 5000]
    assert result["benchmark"] == "synthetic_size_sweep"
    assert len(result["rows"]) == 2
    assert result["rows"][1]["direct_svg_bytes"] > result["rows"][0]["direct_svg_bytes"]
    assert result["rows"][0]["x_uniform"] is True
    assert result["rows"][1]["direct_svg_to_package_ratio"] > 0.0


def test_read_csv_timeseries(tmp_path):
    csv_path = tmp_path / "series.csv"
    csv_path.write_text("time,value\n0,1.0\n1,2.5\n2,3.0\n", encoding="utf-8")

    series = read_csv_timeseries(csv_path, "time", "value")

    assert series.sample_count == 3
    assert np.allclose(series.x, [0.0, 1.0, 2.0])
    assert np.allclose(series.y, [1.0, 2.5, 3.0])


def test_cli_build_synthetic(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vizcompress.cli",
            "build",
            "--synthetic",
            "5000",
            "--fourier-terms",
            "32",
            "--svg-samples",
            "400",
            "--channel",
            "--package",
            "--out",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    summary = json.loads(result.stdout)
    assert summary["input"]["samples"] == 5000
    assert (tmp_path / "rdp_vectorized.svg").exists()
    assert (tmp_path / "fourier_vectorized.svg").exists()
    assert (tmp_path / "fourier_channel.svg").exists()
    assert (tmp_path / "demo.py").exists()
    assert (tmp_path / "metrics.json").exists()
    assert (tmp_path / "model.vizasset" / "asset.json").exists()
    assert "channel" in summary


def test_cli_bench_synthetic(tmp_path):
    output = tmp_path / "bench.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vizcompress.cli",
            "bench",
            "--synthetic-sizes",
            "1000,5000",
            "--fourier-terms",
            "32",
            "--svg-samples",
            "300",
            "--channel",
            "--out",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    summary = json.loads(result.stdout)
    assert output.exists()
    assert summary["rows"][0]["samples"] == 1000
    assert summary["rows"][1]["samples"] == 5000
