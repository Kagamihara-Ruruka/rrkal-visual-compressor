from __future__ import annotations

import json
import subprocess
import sys

import numpy as np

from vizcompress.analyzers import analyze_time_series
from vizcompress.benchmarks import benchmark_synthetic_sizes, parse_sample_sizes
from vizcompress.cleaning import residual_time_series, sigma_clip_time_series, smooth_time_series
from vizcompress.compressors import compress_fourier, compress_fourier_channel, compress_rdp
from vizcompress.core import CompressionReport
from vizcompress.data import SYNTHETIC_KINDS, make_synthetic_dataset, make_synthetic_signal, read_csv_timeseries
from vizcompress.exporters import write_channel_svg, write_demo, write_direct_svg, write_fourier_svg, write_metrics, write_rdp_svg
from vizcompress.packages import load_vizasset_manifest, reconstruct_channel, reconstruct_fourier, write_vizasset
from vizcompress.residuals import analyze_residual, compress_sparse_residual


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


def test_synthetic_dataset_kinds_cover_easy_and_hard_shapes():
    for kind in SYNTHETIC_KINDS:
        series = make_synthetic_dataset(2000, kind=kind)
        profile = analyze_time_series(series)
        assert series.sample_count == 2000
        assert np.isfinite(series.y).all()
        assert profile.x_uniform is (kind != "irregular")


def test_cleaning_and_residual_analysis_preserve_noise_as_layer_candidate():
    series = make_synthetic_dataset(5000, kind="noisy")
    clipped = sigma_clip_time_series(series, sigma=2.0)
    smoothed = smooth_time_series(clipped.cleaned, window=51)
    residual = residual_time_series(series, smoothed.cleaned)
    profile = analyze_residual(series, residual)
    sparse = compress_sparse_residual(clipped.residual)

    assert clipped.cleaned.sample_count == series.sample_count
    assert clipped.metrics["clipped_count"] > 0.0
    assert sparse.parameter_count == int(clipped.metrics["clipped_count"])
    assert smoothed.cleaned.sample_count == series.sample_count
    assert profile.energy_ratio > 0.0
    assert profile.recommended_strategy in {
        "fourier_residual_layer",
        "sparse_outlier_layer",
        "statistical_noise_summary",
    }


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

    direct_svg = write_direct_svg(tmp_path / "direct.svg", series)
    rdp_svg = write_rdp_svg(tmp_path / "rdp.svg", series, rdp)
    fourier_svg = write_fourier_svg(tmp_path / "fourier.svg", series, fourier, samples=800)
    channel_svg = write_channel_svg(tmp_path / "channel.svg", series, channel, samples=800)
    demo = write_demo(tmp_path / "demo.py", series.sample_count, terms=64)
    metrics = write_metrics(
        tmp_path / "metrics.json",
        report,
        [direct_svg.name, rdp_svg.name, fourier_svg.name, channel_svg.name, demo.name],
    )

    assert "Direct SVG" in direct_svg.read_text(encoding="utf-8")
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
    assert manifest["package_profile"] == "retain-residual"
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


def test_vizasset_preserves_irregular_x_domain(tmp_path):
    series = make_synthetic_dataset(3000, kind="irregular")
    rdp = compress_rdp(series, epsilon=0.012)
    fourier = compress_fourier(series, terms=32)
    report = CompressionReport(
        input_samples=series.sample_count,
        rdp=rdp,
        fourier=fourier,
        input_profile=analyze_time_series(series).as_dict(),
    )
    preview = write_fourier_svg(tmp_path / "preview_source.svg", series, fourier, samples=300)
    demo = write_demo(tmp_path / "demo_source.py", series.sample_count, terms=32)
    metrics = write_metrics(tmp_path / "metrics_source.json", report, ["preview_source.svg", "demo_source.py"])

    package = write_vizasset(
        tmp_path / "irregular.vizasset",
        series=series,
        report=report,
        preview_svg=preview,
        metrics_json=metrics,
        demo_py=demo,
    )

    manifest = load_vizasset_manifest(package)
    reconstructed = reconstruct_fourier(package)
    assert manifest["source"]["x_domain_mode"] == "stored_x"
    assert manifest["source"]["profile"]["x_uniform"] is False
    assert np.allclose(reconstructed.x, series.x)


def test_vizasset_can_compress_irregular_x_domain(tmp_path):
    series = make_synthetic_dataset(3000, kind="irregular")
    rdp = compress_rdp(series, epsilon=0.012)
    fourier = compress_fourier(series, terms=32)
    report = CompressionReport(
        input_samples=series.sample_count,
        rdp=rdp,
        fourier=fourier,
        input_profile=analyze_time_series(series).as_dict(),
    )
    preview = write_fourier_svg(tmp_path / "preview_source.svg", series, fourier, samples=300)
    demo = write_demo(tmp_path / "demo_source.py", series.sample_count, terms=32)
    metrics = write_metrics(tmp_path / "metrics_source.json", report, ["preview_source.svg", "demo_source.py"])

    package = write_vizasset(
        tmp_path / "irregular_compressed.vizretain",
        series=series,
        report=report,
        preview_svg=preview,
        metrics_json=metrics,
        demo_py=demo,
        x_domain_policy="compressed",
        x_domain_epsilon=0.002,
    )

    manifest = load_vizasset_manifest(package)
    reconstructed = reconstruct_fourier(package)
    assert manifest["source"]["x_domain_mode"] == "linear_plus_rdp_delta"
    assert manifest["source"]["x_domain"]["parameter_count"] < series.sample_count
    assert np.max(np.abs(reconstructed.x - series.x)) < 0.001


def test_vizasset_auto_x_domain_policy_can_fallback(tmp_path):
    series = make_synthetic_dataset(3000, kind="irregular")
    rdp = compress_rdp(series, epsilon=0.012)
    fourier = compress_fourier(series, terms=32)
    report = CompressionReport(
        input_samples=series.sample_count,
        rdp=rdp,
        fourier=fourier,
        input_profile=analyze_time_series(series).as_dict(),
    )
    preview = write_fourier_svg(tmp_path / "preview_source.svg", series, fourier, samples=300)
    demo = write_demo(tmp_path / "demo_source.py", series.sample_count, terms=32)
    metrics = write_metrics(tmp_path / "metrics_source.json", report, ["preview_source.svg", "demo_source.py"])

    compressed = write_vizasset(
        tmp_path / "auto_compressed.vizretain",
        series=series,
        report=report,
        preview_svg=preview,
        metrics_json=metrics,
        demo_py=demo,
        x_domain_policy="auto",
        x_domain_max_error=1e-3,
    )
    preserved = write_vizasset(
        tmp_path / "auto_preserved.vizretain",
        series=series,
        report=report,
        preview_svg=preview,
        metrics_json=metrics,
        demo_py=demo,
        x_domain_policy="auto",
        x_domain_max_error=1e-12,
    )

    assert load_vizasset_manifest(compressed)["source"]["x_domain_mode"] == "linear_plus_rdp_delta"
    assert load_vizasset_manifest(preserved)["source"]["x_domain_mode"] == "stored_x"


def test_benchmark_reports_size_sweep():
    result = benchmark_synthetic_sizes(
        [1000, 5000],
        synthetic_kind="spikes",
        fourier_terms=32,
        rdp_epsilon=0.012,
        svg_samples=300,
        channel=True,
        channel_k=3.0,
        channel_window=201,
        channel_band_epsilon=0.01,
        smooth_window=11,
        sigma_clip=2.5,
        noise_layer_terms=16,
    )

    assert parse_sample_sizes("1000,5000") == [1000, 5000]
    assert result["benchmark"] == "synthetic_size_sweep"
    assert result["parameters"]["synthetic_kind"] == "spikes"
    assert result["parameters"]["sigma_clip"] == 2.5
    assert result["parameters"]["x_domain_policy"] == "preserve"
    assert "spikes" in result["summary_by_kind"]
    assert "observed_break_even_samples" in result["summary"]
    assert len(result["rows"]) == 2
    assert result["rows"][1]["direct_svg_bytes"] > result["rows"][0]["direct_svg_bytes"]
    assert result["rows"][0]["x_uniform"] is True
    assert result["rows"][0]["x_domain_mode"] == "linspace_from_min_max"
    assert result["rows"][0]["x_domain_max_abs_error"] == 0.0
    assert result["rows"][0]["residual_strategy"] is not None
    assert result["rows"][1]["direct_svg_to_package_ratio"] > 0.0


def test_benchmark_can_run_all_synthetic_kinds():
    result = benchmark_synthetic_sizes(
        [1000],
        synthetic_kind="all",
        fourier_terms=32,
        rdp_epsilon=0.012,
        svg_samples=300,
        channel=False,
        channel_k=3.0,
        channel_window=201,
        channel_band_epsilon=0.01,
    )

    assert len(result["rows"]) == len(SYNTHETIC_KINDS)
    assert {row["synthetic_kind"] for row in result["rows"]} == set(SYNTHETIC_KINDS)
    assert set(result["summary_by_kind"]) == set(SYNTHETIC_KINDS)
    irregular = [row for row in result["rows"] if row["synthetic_kind"] == "irregular"][0]
    assert irregular["x_domain_mode"] == "stored_x"


def test_benchmark_can_use_compressed_x_domain():
    result = benchmark_synthetic_sizes(
        [1000],
        synthetic_kind="irregular",
        fourier_terms=32,
        rdp_epsilon=0.012,
        svg_samples=300,
        channel=False,
        channel_k=3.0,
        channel_window=201,
        channel_band_epsilon=0.01,
        x_domain_policy="compressed",
    )

    assert result["parameters"]["x_domain_policy"] == "compressed"
    assert result["rows"][0]["x_domain_mode"] == "linear_plus_rdp_delta"
    assert result["rows"][0]["x_domain_parameter_count"] < 1000
    assert result["rows"][0]["x_domain_max_abs_error"] < 0.001


def test_benchmark_auto_x_domain_policy_reports_selected_mode():
    result = benchmark_synthetic_sizes(
        [1000],
        synthetic_kind="irregular",
        fourier_terms=32,
        rdp_epsilon=0.012,
        svg_samples=300,
        channel=False,
        channel_k=3.0,
        channel_window=201,
        channel_band_epsilon=0.01,
        x_domain_policy="auto",
        x_domain_max_error=1e-12,
    )

    assert result["parameters"]["x_domain_policy"] == "auto"
    assert result["rows"][0]["x_domain_mode"] == "stored_x"


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
            "--direct-svg",
            "--sigma-clip",
            "2.5",
            "--smooth-window",
            "11",
            "--noise-layer-terms",
            "16",
            "--out",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    summary = json.loads(result.stdout)
    assert summary["input"]["samples"] == 5000
    assert (tmp_path / "direct.svg").exists()
    assert (tmp_path / "rdp_vectorized.svg").exists()
    assert (tmp_path / "fourier_vectorized.svg").exists()
    assert (tmp_path / "fourier_channel.svg").exists()
    assert (tmp_path / "demo.py").exists()
    assert (tmp_path / "metrics.json").exists()
    assert (tmp_path / "model.vizretain" / "asset.json").exists()
    assert "channel" in summary
    assert "noise_layer" in summary
    assert summary["residual"]["recommended_strategy"] is not None


def test_cli_build_clean_package_profile_drops_residual_layers(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vizcompress.cli",
            "build",
            "--synthetic",
            "5000",
            "--synthetic-kind",
            "spikes",
            "--sigma-clip",
            "2.5",
            "--auto-noise-layer",
            "--package",
            "--package-profile",
            "clean",
            "--out",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    summary = json.loads(result.stdout)
    manifest = load_vizasset_manifest(tmp_path / "model.vizclean")
    assert summary["residual"]["recommended_strategy"] == "sparse_outlier_layer"
    assert manifest["package_profile"] == "clean"
    assert "sparse_residual_layer" in summary
    assert "sparse_residual_layer" not in manifest["metrics"]


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
            "--synthetic-kind",
            "spikes",
            "--fourier-terms",
            "32",
            "--svg-samples",
            "300",
            "--channel",
            "--sigma-clip",
            "2.5",
            "--auto-noise-layer",
            "--out",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    summary = json.loads(result.stdout)
    assert output.exists()
    assert "summary" in summary
    assert summary["parameters"]["auto_noise_layer"] is True
    assert summary["rows"][0]["samples"] == 1000
    assert summary["rows"][0]["residual_strategy"] == "sparse_outlier_layer"
    assert summary["rows"][0]["sparse_residual_parameter_count"] is not None
    assert summary["rows"][1]["samples"] == 5000


def test_cli_inspect_vizasset(tmp_path):
    subprocess.run(
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

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vizcompress.cli",
            "inspect",
            str(tmp_path / "model.vizretain"),
            "--samples",
            "300",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    summary = json.loads(result.stdout)
    assert summary["primary_method"] == "fourier_channel"
    assert summary["package_profile"] == "retain-residual"
    assert summary["reconstructed"]["samples"] == 300
    assert summary["channel"]["samples"] == 300


def test_cli_inspect_reports_clean_profile_without_residual_layer(tmp_path):
    subprocess.run(
        [
            sys.executable,
            "-m",
            "vizcompress.cli",
            "build",
            "--synthetic",
            "5000",
            "--synthetic-kind",
            "spikes",
            "--sigma-clip",
            "2.5",
            "--auto-noise-layer",
            "--package",
            "--package-profile",
            "clean",
            "--out",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vizcompress.cli",
            "inspect",
            str(tmp_path / "model.vizclean"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    summary = json.loads(result.stdout)
    assert summary["package_profile"] == "clean"
    assert summary["contains_sparse_residual_layer"] is False
