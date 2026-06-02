from __future__ import annotations

import json
import importlib.util
import sys
from pathlib import Path

import numpy as np

from _test_helpers import cli_env as _cli_test_env, run_cli as _run_cli, script_path as _repo_script

ROOT_DIR = Path(__file__).resolve().parents[1]


from vizcompress.analyzers import analyze_time_series
from vizcompress.benchmarks import (
    benchmark_synthetic_channel_k,
    benchmark_synthetic_fourier_terms,
    benchmark_synthetic_sizes,
    benchmark_synthetic_terms_channel_k_sweep,
    evaluate_benchmark_gate,
    format_benchmark_markdown,
    parse_float_values,
    parse_fourier_terms,
    parse_sample_sizes,
)
from vizcompress.cleaning import residual_time_series, sigma_clip_time_series, smooth_time_series
from vizcompress.compressors import compress_fourier, compress_fourier_channel, compress_lttb, compress_rdp, lttb_indices
from vizcompress.core import CompressionReport
from vizcompress.data import SYNTHETIC_KINDS, make_synthetic_dataset, make_synthetic_signal, read_csv_timeseries
from vizcompress.exporters import write_channel_svg, write_demo, write_direct_svg, write_fourier_svg, write_metrics, write_rdp_svg
from vizcompress import __version__
from vizcompress.packages import (
    load_vizasset_manifest,
    ASSET_SCHEMA_VERSION,
    reconstruct_channel,
    reconstruct_fourier,
    reconstruct_noise_layer,
    reconstruct_retained_signal,
    reconstruct_sparse_residual,
    validate_vizasset,
    validate_vizasset_source,
    write_vizasset,
)
from vizcompress.residuals import analyze_residual, compress_sparse_residual
from vizcompress.reviews import build_review_packet, package_size_summary, source_fingerprint, write_review_packet
from vizcompress.selectors import count_recommendations, recommend_benchmark_row, recommend_benchmark_row_gzip


def test_rdp_and_fourier_compress_synthetic_series():
    series = make_synthetic_signal(20_000)

    rdp = compress_rdp(series, epsilon=0.012)
    fourier = compress_fourier(series, terms=96)

    assert 2 < rdp.parameter_count < series.sample_count
    assert fourier.parameter_count == 96
    assert rdp.metrics["r2"] > 0.9
    assert fourier.metrics["r2"] > 0.99


def test_lttb_downsampling_baseline_keeps_order_and_endpoints():
    series = make_synthetic_signal(20_000)

    indices = lttb_indices(series.x, series.y, threshold=800)
    lttb = compress_lttb(series, threshold=800)

    assert indices.shape == (800,)
    assert indices[0] == 0
    assert indices[-1] == series.sample_count - 1
    assert np.all(np.diff(indices) > 0)
    assert lttb.parameter_count == 800
    assert lttb.metrics["r2"] > 0.95


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


def test_cli_mvp_writes_demo_package_benchmark_and_summary(tmp_path):
    output_dir = tmp_path / "mvp"
    cmd = [
        sys.executable,
        "-m",
        "vizcompress.cli",
        "mvp",
        "--samples",
        "1200",
        "--synthetic-kind",
        "smooth",
        "--fourier-terms",
        "32",
        "--svg-samples",
        "240",
        "--out",
        str(output_dir),
        "--min-fourier-r2",
        "0.9",
    ]

    result = _run_cli(
        cmd,
        cwd=ROOT_DIR,
        env=_cli_test_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    summary_path = output_dir / "mvp_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "pass"
    assert summary["validation"]["package_ok"] is True
    assert summary["validation"]["source_ok"] is True
    assert summary["benchmark_gate"]["ok"] is True
    assert (output_dir / "asset" / "model.vizretain" / "asset.json").exists()
    assert (output_dir / "asset" / "fourier_channel.svg").exists()
    assert (output_dir / "asset" / "demo.py").exists()
    assert (output_dir / "benchmark.json").exists()
    assert (output_dir / "benchmark.md").exists()


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
    assert manifest["schema_version"] == ASSET_SCHEMA_VERSION
    assert manifest["generated_by"]["tool"] == "rrkal.visual_compressor"
    assert manifest["generated_by"]["version"] == __version__
    assert manifest["compatibility"]["schema"] == "rrkal_visual_compressor.package_profile.v0"
    assert manifest["compatibility"]["package_kind"] == "vizasset"
    assert manifest["compatibility"]["renderability"]["preview_only"] is True
    assert manifest["compatibility"]["renderability"]["reconstructable"] is True
    assert manifest["compatibility"]["renderability"]["renderer_native"] is False
    assert manifest["asset_type"] == "rrkal.visual_compressor.timeseries"
    assert manifest["model"]["profile"] == "fourier_channel"
    assert manifest["package_profile"] == "retain-residual"
    assert manifest["model"]["primary_method"] == "fourier_channel"
    assert manifest["source"]["profile"]["x_uniform"] is True
    assert manifest["files"]["model"]["path"] == "model.npz"
    assert len(manifest["files"]["preview"]["sha256"]) == 64
    assert (package / "asset.json").exists()
    assert (package / "model.npz").exists()
    assert (package / "preview.svg").exists()


def test_write_vizasset_includes_review_file_metadata_when_provided(tmp_path):
    series = make_synthetic_signal(2000)
    rdp = compress_rdp(series, epsilon=0.012)
    fourier = compress_fourier(series, terms=48)
    report = CompressionReport(input_samples=series.sample_count, rdp=rdp, fourier=fourier)

    package_path = tmp_path / "model.vizasset"
    package_path.mkdir(parents=True)
    review_path = package_path / "review.json"
    review_payload = {
        "schema_version": "0.1",
        "review_type": "rrkal.visual_compressor.package_review",
        "accepted": True,
    }
    review_path.write_text(json.dumps(review_payload), encoding="utf-8")
    preview = write_fourier_svg(
        tmp_path / "preview_source.svg",
        series,
        fourier,
        samples=300,
    )
    demo = write_demo(tmp_path / "demo_source.py", series.sample_count, terms=48)
    metrics = write_metrics(tmp_path / "metrics_source.json", report, ["preview_source.svg", "demo_source.py"])

    package = write_vizasset(
        package_path,
        series=series,
        report=report,
        preview_svg=preview,
        metrics_json=metrics,
        demo_py=demo,
        review_json=review_path,
    )

    manifest = load_vizasset_manifest(package)
    assert "review" in manifest["files"]
    assert manifest["files"]["review"]["path"] == "review.json"
    assert len(manifest["files"]["review"]["sha256"]) == 64


def test_validate_vizasset_package_checks_hashes_and_reconstruction(tmp_path):
    series = make_synthetic_signal(5000)
    rdp = compress_rdp(series, epsilon=0.012)
    fourier = compress_fourier(series, terms=48)
    report = CompressionReport(input_samples=series.sample_count, rdp=rdp, fourier=fourier)
    preview = write_fourier_svg(tmp_path / "preview_source.svg", series, fourier, samples=400)
    demo = write_demo(tmp_path / "demo_source.py", series.sample_count, terms=48)
    metrics = write_metrics(tmp_path / "metrics_source.json", report, ["preview_source.svg", "demo_source.py"])
    package = write_vizasset(
        tmp_path / "valid.vizasset",
        series=series,
        report=report,
        preview_svg=preview,
        metrics_json=metrics,
        demo_py=demo,
    )

    result = validate_vizasset(package, reconstruction_samples=256)

    assert result.ok is True
    assert result.errors == ()
    assert result.details["sample_count"] == series.sample_count
    assert result.details["validated_reconstruction_samples"] == 256


def test_validate_vizasset_rejects_drifted_artifact(tmp_path):
    series = make_synthetic_signal(3000)
    rdp = compress_rdp(series, epsilon=0.012)
    fourier = compress_fourier(series, terms=32)
    report = CompressionReport(input_samples=series.sample_count, rdp=rdp, fourier=fourier)
    preview = write_fourier_svg(tmp_path / "preview_source.svg", series, fourier, samples=300)
    demo = write_demo(tmp_path / "demo_source.py", series.sample_count, terms=32)
    metrics = write_metrics(tmp_path / "metrics_source.json", report, ["preview_source.svg", "demo_source.py"])
    package = write_vizasset(
        tmp_path / "drifted.vizasset",
        series=series,
        report=report,
        preview_svg=preview,
        metrics_json=metrics,
        demo_py=demo,
    )
    (package / "preview.svg").write_text("<svg></svg>\n", encoding="utf-8")

    result = validate_vizasset(package, reconstruction_samples=128)

    assert result.ok is False
    assert any("files.preview" in error for error in result.errors)


def test_validate_vizasset_source_reports_fidelity_metrics(tmp_path):
    series = make_synthetic_signal(5000)
    rdp = compress_rdp(series, epsilon=0.012)
    fourier = compress_fourier(series, terms=96)
    report = CompressionReport(input_samples=series.sample_count, rdp=rdp, fourier=fourier)
    preview = write_fourier_svg(tmp_path / "preview_source.svg", series, fourier, samples=400)
    demo = write_demo(tmp_path / "demo_source.py", series.sample_count, terms=96)
    metrics = write_metrics(tmp_path / "metrics_source.json", report, ["preview_source.svg", "demo_source.py"])
    package = write_vizasset(
        tmp_path / "source_verified.vizasset",
        series=series,
        report=report,
        preview_svg=preview,
        metrics_json=metrics,
        demo_py=demo,
    )

    result = validate_vizasset_source(package, series, max_rmse=0.003, max_mae=0.001, max_error=0.05)

    assert result.ok is True
    source_details = result.details["source_verification"]
    assert source_details["sample_count"] == series.sample_count
    assert source_details["rmse"] < 0.003
    assert source_details["x_max_abs_error"] == 0.0


def test_validate_vizasset_source_fails_strict_budget_for_wrong_source(tmp_path):
    series = make_synthetic_dataset(5000, kind="smooth")
    wrong_source = make_synthetic_dataset(5000, kind="steps")
    rdp = compress_rdp(series, epsilon=0.012)
    fourier = compress_fourier(series, terms=96)
    report = CompressionReport(input_samples=series.sample_count, rdp=rdp, fourier=fourier)
    preview = write_fourier_svg(tmp_path / "preview_source.svg", series, fourier, samples=400)
    demo = write_demo(tmp_path / "demo_source.py", series.sample_count, terms=96)
    metrics = write_metrics(tmp_path / "metrics_source.json", report, ["preview_source.svg", "demo_source.py"])
    package = write_vizasset(
        tmp_path / "wrong_source.vizasset",
        series=series,
        report=report,
        preview_svg=preview,
        metrics_json=metrics,
        demo_py=demo,
    )

    result = validate_vizasset_source(package, wrong_source, max_rmse=0.01)

    assert result.ok is False
    assert any("rmse" in error for error in result.errors)


def test_review_packet_records_source_fingerprint_and_acceptance(tmp_path):
    series = make_synthetic_signal(5000)
    rdp = compress_rdp(series, epsilon=0.012)
    fourier = compress_fourier(series, terms=96)
    report = CompressionReport(input_samples=series.sample_count, rdp=rdp, fourier=fourier)
    preview = write_fourier_svg(tmp_path / "preview_source.svg", series, fourier, samples=400)
    direct = write_direct_svg(tmp_path / "direct.svg", series)
    demo = write_demo(tmp_path / "demo_source.py", series.sample_count, terms=96)
    metrics = write_metrics(tmp_path / "metrics_source.json", report, ["preview_source.svg", "demo_source.py"])
    package = write_vizasset(
        tmp_path / "reviewed.vizasset",
        series=series,
        report=report,
        preview_svg=preview,
        metrics_json=metrics,
        demo_py=demo,
    )

    packet = build_review_packet(
        package,
        series,
        baseline_files={"direct_svg": direct},
        max_rmse=0.003,
        max_error=0.05,
    )
    output = write_review_packet(
        tmp_path / "review.json",
        package,
        series,
        baseline_files={"direct_svg": direct},
        max_rmse=0.003,
        max_error=0.05,
    )
    written = json.loads(output.read_text(encoding="utf-8"))

    assert source_fingerprint(series)["xy_sha256"] == packet["source_fingerprint"]["xy_sha256"]
    assert packet["accepted"] is True
    assert written["accepted"] is True
    assert written["size_evidence"]["package_bytes"] > 0
    assert written["size_evidence"]["source_numeric_bytes"] == series.x.nbytes + series.y.nbytes
    assert package_size_summary(package, series)["file_count"] >= 4
    assert packet["baseline_evidence"]["direct_svg"]["present"] is True
    assert written["baseline_evidence"]["direct_svg"]["baseline_to_package_ratio"] > 0.0
    assert written["baseline_evidence"]["direct_svg"]["gzip_bytes"] > 0
    assert written["baseline_evidence"]["direct_svg"]["gzip_to_package_ratio"] > 0.0
    assert written["source_validation"]["details"]["source_verification"]["rmse"] < 0.003


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


def test_vizasset_reconstructs_sparse_residual_layer(tmp_path):
    series = make_synthetic_dataset(5000, kind="spikes")
    clipped = sigma_clip_time_series(series, sigma=2.5)
    cleaned = clipped.cleaned
    residual = residual_time_series(series, cleaned)
    rdp = compress_rdp(cleaned, epsilon=0.012)
    fourier = compress_fourier(cleaned, terms=48)
    sparse = compress_sparse_residual(residual)
    report = CompressionReport(
        input_samples=cleaned.sample_count,
        rdp=rdp,
        fourier=fourier,
        input_profile=analyze_time_series(cleaned).as_dict(),
        sparse_residual=sparse,
        residual_profile=analyze_residual(series, residual).as_dict(),
    )
    preview = write_fourier_svg(tmp_path / "preview_source.svg", cleaned, fourier, samples=300)
    demo = write_demo(tmp_path / "demo_source.py", cleaned.sample_count, terms=48)
    metrics = write_metrics(tmp_path / "metrics_source.json", report, ["preview_source.svg", "demo_source.py"])
    package = write_vizasset(
        tmp_path / "sparse.vizretain",
        series=cleaned,
        report=report,
        preview_svg=preview,
        metrics_json=metrics,
        demo_py=demo,
    )

    reconstructed = reconstruct_sparse_residual(package)
    retained = reconstruct_retained_signal(package)
    assert reconstructed["indices"].shape[0] == sparse.parameter_count
    assert np.allclose(reconstructed["delta_y"], sparse.delta_y)
    assert retained.sample_count == cleaned.sample_count


def test_vizasset_reconstructs_fourier_noise_layer(tmp_path):
    series = make_synthetic_dataset(5000, kind="noisy")
    smoothed = smooth_time_series(series, window=51)
    cleaned = smoothed.cleaned
    residual = residual_time_series(series, cleaned)
    rdp = compress_rdp(cleaned, epsilon=0.012)
    fourier = compress_fourier(cleaned, terms=48)
    noise = compress_fourier(residual, terms=16)
    report = CompressionReport(
        input_samples=cleaned.sample_count,
        rdp=rdp,
        fourier=fourier,
        input_profile=analyze_time_series(cleaned).as_dict(),
        noise=noise,
        residual_profile=analyze_residual(series, residual).as_dict(),
    )
    preview = write_fourier_svg(tmp_path / "preview_source.svg", cleaned, fourier, samples=300)
    demo = write_demo(tmp_path / "demo_source.py", cleaned.sample_count, terms=48)
    metrics = write_metrics(tmp_path / "metrics_source.json", report, ["preview_source.svg", "demo_source.py"])
    package = write_vizasset(
        tmp_path / "noise.vizretain",
        series=cleaned,
        report=report,
        preview_svg=preview,
        metrics_json=metrics,
        demo_py=demo,
    )

    reconstructed = reconstruct_noise_layer(package, samples=300)
    retained = reconstruct_retained_signal(package, samples=300)
    assert reconstructed.sample_count == 300
    assert np.isfinite(reconstructed.y).all()
    assert retained.sample_count == 300
    assert np.isfinite(retained.y).all()


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
    assert "recommendation_counts" in result["summary"]
    assert "observed_break_even_samples" in result["summary"]
    assert "package_wins_against_direct_svg_gzip_count" in result["summary"]
    assert "package_wins_against_source_csv_gzip_count" in result["summary"]
    assert "best_source_csv_gzip_to_package_ratio" in result["summary"]
    assert "best_rows" in result["summary"]
    assert "best_defensible_high_fidelity_svg_gzip_candidate" in result["summary"]
    assert "best_high_fidelity_svg_gzip_candidate" in result["summary"]
    assert len(result["rows"]) == 2
    assert result["rows"][1]["direct_svg_bytes"] > result["rows"][0]["direct_svg_bytes"]
    assert result["rows"][1]["direct_svg_gzip_bytes"] > result["rows"][0]["direct_svg_gzip_bytes"]
    assert result["rows"][1]["source_csv_bytes"] > result["rows"][0]["source_csv_bytes"]
    assert result["rows"][1]["source_csv_gzip_bytes"] > result["rows"][0]["source_csv_gzip_bytes"]
    assert result["rows"][0]["lttb_svg_bytes"] > 0
    assert result["rows"][0]["lttb_svg_gzip_bytes"] > 0
    assert result["rows"][0]["x_uniform"] is True
    assert result["rows"][0]["x_domain_mode"] == "linspace_from_min_max"
    assert result["rows"][0]["x_domain_max_abs_error"] == 0.0
    assert "recommendation" in result["rows"][0]
    assert "gzip_recommendation" in result["rows"][0]
    assert result["rows"][0]["residual_strategy"] is not None
    assert result["rows"][1]["direct_svg_to_package_ratio"] > 0.0
    assert result["rows"][1]["direct_svg_gzip_to_package_ratio"] > 0.0
    assert result["rows"][1]["source_csv_to_package_ratio"] > 0.0
    assert result["rows"][1]["source_csv_gzip_to_package_ratio"] > 0.0
    assert result["rows"][0]["lttb_parameter_count"] == 300
    assert result["rows"][0]["lttb_r2"] > 0.0
    assert result["rows"][0]["lttb_svg_to_package_ratio"] > 0.0
    assert result["rows"][0]["lttb_svg_gzip_to_package_ratio"] > 0.0
    assert "gzip_recommendation_counts" in result["summary"]


def test_benchmark_markdown_report_includes_baseline_evidence():
    result = benchmark_synthetic_sizes(
        [1000],
        synthetic_kind="smooth",
        fourier_terms=32,
        rdp_epsilon=0.012,
        svg_samples=300,
        channel=True,
        channel_k=3.0,
        channel_window=201,
        channel_band_epsilon=0.01,
    )

    report = format_benchmark_markdown(result)

    assert "# VizCompress Benchmark Report" in report
    assert "SVG.gz/package" in report
    assert "CSV.gz/package" in report
    assert "LTTB SVG.gz/package" in report
    assert "Best defensible high-fidelity SVG.gz candidate" in report
    assert "Best high-fidelity SVG.gz candidate" in report
    assert "High-fidelity rows (R2>=0.99)" in report
    assert "Defensible rows (coverage>=" in report
    assert "Defensible rows" in report
    assert "samples /" in report
    assert "package must also pass source verification" in report

    result["benchmark_gate"] = evaluate_benchmark_gate(result, min_fourier_r2=0.99)
    gated_report = format_benchmark_markdown(result)
    assert "## Benchmark Gate" in gated_report
    assert "OK:" in gated_report


def test_defensible_ratio_is_consistent_with_rows():
    result = benchmark_synthetic_sizes(
        [1000],
        synthetic_kind="smooth",
        fourier_terms=32,
        rdp_epsilon=0.6,
        svg_samples=240,
        channel=True,
        channel_k=3.0,
        channel_window=16,
        channel_band_epsilon=0.04,
        defensible_channel_coverage_threshold=0.99,
    )
    summary = result["summary"]

    assert summary["high_fidelity_rows_count"] >= 1
    assert summary["defensible_rows_count"] <= summary["high_fidelity_rows_count"]
    assert summary["defensible_rows_ratio"] == 0.0
    assert summary["defensible_rows_count"] == 0
    assert "Defensible rows (coverage>= 0.99): `0 (0%)`" in format_benchmark_markdown(result)


def test_benchmark_can_sweep_fourier_terms():
    result = benchmark_synthetic_fourier_terms(
        [1000],
        fourier_terms_values=[16, 32],
        synthetic_kind="smooth",
        rdp_epsilon=0.012,
        svg_samples=300,
        channel=False,
        channel_k=3.0,
        channel_window=201,
        channel_band_epsilon=0.01,
    )

    assert parse_fourier_terms("16,32") == [16, 32]
    assert result["benchmark"] == "synthetic_fourier_terms_sweep"
    assert len(result["rows"]) == 2
    assert {row["fourier_terms"] for row in result["rows"]} == {16, 32}
    assert set(result["summary_by_terms"]) == {"16", "32"}
    assert result["rows"][1]["fourier_parameter_count"] == 32
    assert result["summary_by_terms"]["32"]["best_rows"]["direct_svg_gzip"]["fourier_terms"] == 32
    assert "terms" in format_benchmark_markdown(result)


def test_benchmark_can_sweep_channel_k():
    result = benchmark_synthetic_channel_k(
        [1000],
        channel_k_values=[2.0, 3.0],
        synthetic_kind="smooth",
        fourier_terms=32,
        rdp_epsilon=0.012,
        svg_samples=300,
        channel_window=201,
        channel_band_epsilon=0.01,
    )

    assert parse_float_values("2,3", name="channel K", minimum=0.0) == [2.0, 3.0]
    assert result["benchmark"] == "synthetic_channel_k_sweep"
    assert len(result["rows"]) == 2
    assert {row["channel_k"] for row in result["rows"]} == {2.0, 3.0}
    assert set(result["summary_by_channel_k"]) == {"2", "3"}
    assert result["rows"][1]["channel_coverage_ratio"] >= result["rows"][0]["channel_coverage_ratio"]
    assert "channel K" in format_benchmark_markdown(result)


def test_benchmark_summary_prefers_defensible_high_fidelity_candidates():
    result = benchmark_synthetic_channel_k(
        [1000],
        channel_k_values=[2.0, 3.0, 4.0],
        synthetic_kind="smooth",
        fourier_terms=32,
        rdp_epsilon=0.012,
        svg_samples=300,
        channel_window=201,
        channel_band_epsilon=0.01,
        defensible_channel_coverage_threshold=0.98,
    )

    candidate = result["summary"]["best_defensible_high_fidelity_svg_gzip_candidate"]
    assert candidate is not None
    assert candidate["fourier_r2"] >= 0.99
    assert candidate["channel_coverage_ratio"] >= 0.98
    assert candidate["channel_k"] in {3.0, 4.0}


def test_benchmark_can_sweep_fourier_terms_and_channel_k_grid():
    result = benchmark_synthetic_terms_channel_k_sweep(
        [1000],
        fourier_terms_values=[16, 32],
        channel_k_values=[2.0, 3.0],
        synthetic_kind="smooth",
        rdp_epsilon=0.012,
        svg_samples=300,
        channel_window=201,
        channel_band_epsilon=0.01,
    )

    assert result["benchmark"] == "synthetic_terms_channel_k_sweep"
    assert len(result["rows"]) == 4
    assert set(result["summary_by_terms"]) == {"16", "32"}
    assert set(result["summary_by_channel_k"]) == {"2", "3"}
    assert "16|2" in result["summary_by_terms_k"]
    assert "16|3" in result["summary_by_terms_k"]
    assert "32|2" in result["summary_by_terms_k"]
    assert "32|3" in result["summary_by_terms_k"]
    assert "defensible_rows_count" in result["summary_by_terms_k"]["16|2"]


def test_benchmark_gate_checks_size_and_fidelity_policy():
    result = benchmark_synthetic_sizes(
        [1000],
        synthetic_kind="smooth",
        fourier_terms=32,
        rdp_epsilon=0.012,
        svg_samples=300,
        channel=False,
        channel_k=3.0,
        channel_window=201,
        channel_band_epsilon=0.01,
    )

    passing = evaluate_benchmark_gate(result, min_fourier_r2=0.8)
    failing = evaluate_benchmark_gate(
        result,
        require_svg_gzip_win=True,
        min_fourier_r2=1.01,
        min_channel_coverage=0.99,
    )

    assert passing["ok"] is True
    assert failing["ok"] is False
    assert failing["policy"]["require_svg_gzip_win"] is True
    assert failing["policy"]["min_channel_coverage"] == 0.99
    assert failing["errors"]


def test_selector_recommends_from_benchmark_row_shape():
    row = {
        "direct_svg_to_package_ratio": 4.0,
        "fourier_r2": 0.9,
        "x_domain_mode": "linspace_from_min_max",
        "x_domain_parameter_count": 2.0,
        "fourier_parameter_count": 32,
        "channel_coverage_ratio": None,
    }

    assert recommend_benchmark_row(row) == "package_smaller_but_low_fidelity"
    row["direct_svg_gzip_to_package_ratio"] = 0.5
    assert recommend_benchmark_row_gzip(row) == "package_beats_raw_svg_but_not_gzip"
    assert count_recommendations([{"recommendation": "package_preferred"}, {"recommendation": "package_preferred"}]) == {
        "package_preferred": 2
    }
    assert count_recommendations(
        [{"gzip_recommendation": "direct_svg_gzip_preferred"}],
        field="gzip_recommendation",
    ) == {"direct_svg_gzip_preferred": 1}


def test_selector_recommends_with_gzip_only_ratio_fields():
    row = {
        "direct_svg_gzip_to_package_ratio": 1.8,
        "fourier_r2": 0.99,
        "x_domain_mode": "stored_x",
        "x_domain_parameter_count": 2.0,
        "fourier_parameter_count": 32,
        "channel_coverage_ratio": 0.95,
    }

    assert recommend_benchmark_row(row) == "package_preferred"
    assert recommend_benchmark_row_gzip(row) == "package_preferred_against_gzip"


def test_selector_recommendation_keeps_string_fields_robust():
    row = {
        "direct_svg_to_package_ratio": "bad",
        "direct_svg_gzip_to_package_ratio": "2.2",
        "fourier_r2": 0.97,
        "x_domain_mode": "stored_x",
        "x_domain_parameter_count": 2.0,
        "fourier_parameter_count": 32,
        "channel_coverage_ratio": 0.95,
    }

    assert recommend_benchmark_row(row) == "package_preferred"
    assert recommend_benchmark_row_gzip(row) == "package_preferred_against_gzip"


def test_selector_recommendation_rejects_bool_ratio_fields():
    row = {
        "direct_svg_to_package_ratio": True,
        "direct_svg_gzip_to_package_ratio": "2.2",
        "fourier_r2": 0.97,
        "x_domain_mode": "stored_x",
        "x_domain_parameter_count": 2.0,
        "fourier_parameter_count": 32,
        "channel_coverage_ratio": 0.95,
    }

    assert recommend_benchmark_row(row) == "package_preferred"
    assert recommend_benchmark_row_gzip(row) == "package_preferred_against_gzip"


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
    assert all("recommendation_counts" in value for value in result["summary_by_kind"].values())
    assert all("gzip_recommendation_counts" in value for value in result["summary_by_kind"].values())
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
    assert result["rows"][0]["recommendation"] in {
        "direct_svg_preferred",
        "package_wins_but_domain_heavy",
    }


def test_read_csv_timeseries(tmp_path):
    csv_path = tmp_path / "series.csv"
    csv_path.write_text("time,value\n0,1.0\n1,2.5\n2,3.0\n", encoding="utf-8")

    series = read_csv_timeseries(csv_path, "time", "value")

    assert series.sample_count == 3
    assert np.allclose(series.x, [0.0, 1.0, 2.0])
    assert np.allclose(series.y, [1.0, 2.5, 3.0])


def test_cli_build_synthetic(tmp_path):
    result = _run_cli(
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
        env=_cli_test_env(),
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
    result = _run_cli(
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
        env=_cli_test_env(),
    )

    summary = json.loads(result.stdout)
    manifest = load_vizasset_manifest(tmp_path / "model.vizclean")
    assert summary["residual"]["recommended_strategy"] == "sparse_outlier_layer"
    assert manifest["package_profile"] == "clean"
    assert "sparse_residual_layer" in summary
    assert "sparse_residual_layer" not in manifest["metrics"]


def test_cli_bench_synthetic(tmp_path):
    output = tmp_path / "bench.json"
    report = tmp_path / "bench.md"
    result = _run_cli(
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
            "--report-md",
            str(report),
            "--min-fourier-r2",
            "0.8",
            "--min-channel-coverage",
            "0.1",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=_cli_test_env(),
    )

    summary = json.loads(result.stdout)
    assert output.exists()
    assert report.exists()
    assert "summary" in summary
    assert summary["markdown_report"] == str(report)
    assert summary["benchmark_gate"]["ok"] is True
    assert summary["benchmark_gate"]["policy"]["min_channel_coverage"] == 0.1
    assert summary["parameters"]["auto_noise_layer"] is True
    assert summary["rows"][0]["samples"] == 1000
    assert summary["rows"][0]["residual_strategy"] == "sparse_outlier_layer"
    assert summary["rows"][0]["sparse_residual_parameter_count"] is not None
    assert summary["rows"][1]["samples"] == 5000
    assert "LTTB SVG.gz/package" in report.read_text(encoding="utf-8")


def test_cli_bench_can_sweep_fourier_terms(tmp_path):
    output = tmp_path / "terms.json"
    result = _run_cli(
        [
            sys.executable,
            "-m",
            "vizcompress.cli",
            "bench",
            "--synthetic-sizes",
            "1000",
            "--synthetic-kind",
            "smooth",
            "--fourier-terms-sweep",
            "16,32",
            "--svg-samples",
            "300",
            "--out",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=_cli_test_env(),
    )

    summary = json.loads(result.stdout)
    assert summary["benchmark"] == "synthetic_fourier_terms_sweep"
    assert summary["parameters"]["fourier_terms_values"] == [16, 32]
    assert set(summary["summary_by_terms"]) == {"16", "32"}


def test_cli_bench_can_sweep_channel_k(tmp_path):
    output = tmp_path / "channel_k.json"
    result = _run_cli(
        [
            sys.executable,
            "-m",
            "vizcompress.cli",
            "bench",
            "--synthetic-sizes",
            "1000",
            "--synthetic-kind",
            "smooth",
            "--fourier-terms",
            "32",
            "--channel-k-sweep",
            "2,3",
            "--svg-samples",
            "300",
            "--out",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=_cli_test_env(),
    )

    summary = json.loads(result.stdout)
    assert summary["benchmark"] == "synthetic_channel_k_sweep"
    assert summary["parameters"]["channel_k_values"] == [2.0, 3.0]
    assert summary["parameters"]["defensible_channel_coverage_threshold"] == 0.9
    assert set(summary["summary_by_channel_k"]) == {"2", "3"}


def test_cli_bench_can_sweep_fourier_terms_and_channel_k(tmp_path):
    output = tmp_path / "terms_k.json"
    result = _run_cli(
        [
            sys.executable,
            "-m",
            "vizcompress.cli",
            "bench",
            "--synthetic-sizes",
            "1000",
            "--synthetic-kind",
            "smooth",
            "--fourier-terms-sweep",
            "16,32",
            "--channel-k-sweep",
            "2,3",
            "--channel",
            "--svg-samples",
            "300",
            "--out",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=_cli_test_env(),
    )

    summary = json.loads(result.stdout)
    assert summary["benchmark"] == "synthetic_terms_channel_k_sweep"
    assert summary["parameters"]["fourier_terms_values"] == [16, 32]
    assert summary["parameters"]["channel_k_values"] == [2.0, 3.0]
    assert summary["parameters"]["channel"] is True
    assert set(summary["summary_by_terms_k"].keys()) == {"16|2", "16|3", "32|2", "32|3"}


def test_cli_bench_accepts_defensible_coverage_threshold(tmp_path):
    output = tmp_path / "channel_k_threshold.json"
    result = _run_cli(
        [
            sys.executable,
            "-m",
            "vizcompress.cli",
            "bench",
            "--synthetic-sizes",
            "10000",
            "--synthetic-kind",
            "smooth",
            "--fourier-terms",
            "32",
            "--channel-k-sweep",
            "2,3",
            "--defensible-channel-coverage",
            "0.98",
            "--svg-samples",
            "300",
            "--out",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    summary = json.loads(result.stdout)
    assert summary["parameters"]["defensible_channel_coverage_threshold"] == 0.98
    assert summary["summary"]["defensible_channel_coverage_threshold"] == 0.98
    candidate = summary["summary"]["best_defensible_high_fidelity_svg_gzip_candidate"]
    assert candidate["channel_coverage_ratio"] >= 0.98
    assert summary["summary_by_kind"]["smooth"]["defensible_channel_coverage_threshold"] == 0.98
    assert (
        summary["summary_by_channel_k"]["3"]["best_defensible_high_fidelity_svg_gzip_candidate"][
            "channel_coverage_ratio"
        ]
        >= 0.98
    )
    assert (
        summary["summary_by_channel_k"]["2"]["best_defensible_high_fidelity_svg_gzip_candidate"] is None
    )


def test_cli_bench_accepts_defensible_coverage_threshold_in_fourier_terms_sweep(tmp_path):
    output = tmp_path / "fourier_terms_threshold.json"
    result = _run_cli(
        [
            sys.executable,
            "-m",
            "vizcompress.cli",
            "bench",
            "--synthetic-sizes",
            "10000",
            "--synthetic-kind",
            "smooth",
            "--fourier-terms-sweep",
            "16,32",
            "--channel",
            "--channel-k",
            "3",
            "--defensible-channel-coverage",
            "0.995",
            "--svg-samples",
            "240",
            "--out",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    summary = json.loads(result.stdout)
    assert summary["parameters"]["defensible_channel_coverage_threshold"] == 0.995
    assert summary["summary"]["defensible_channel_coverage_threshold"] == 0.995
    assert summary["summary_by_terms"]["16"]["defensible_channel_coverage_threshold"] == 0.995
    assert summary["summary_by_terms"]["32"]["defensible_channel_coverage_threshold"] == 0.995
    assert (
        summary["summary_by_terms"]["16"]["best_defensible_high_fidelity_svg_gzip_candidate"][
            "channel_coverage_ratio"
        ]
        >= 0.995
    )
    assert (
        summary["summary_by_terms"]["32"]["best_defensible_high_fidelity_svg_gzip_candidate"][
            "channel_coverage_ratio"
        ]
        >= 0.995
    )


def test_cli_bench_gate_can_fail(tmp_path):
    output = tmp_path / "bench.json"
    result = _run_cli(
        [
            sys.executable,
            "-m",
            "vizcompress.cli",
            "bench",
            "--synthetic-sizes",
            "1000",
            "--synthetic-kind",
            "smooth",
            "--fourier-terms",
            "32",
            "--svg-samples",
            "300",
            "--out",
            str(output),
            "--min-fourier-r2",
            "1.01",
            "--min-channel-coverage",
            "0.99",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    summary = json.loads(result.stdout)
    assert result.returncode == 1
    assert output.exists()
    assert summary["benchmark_gate"]["ok"] is False
    assert summary["benchmark_gate"]["policy"]["min_channel_coverage"] == 0.99


def test_cli_recommend_reads_benchmark_json(tmp_path):
    output = tmp_path / "bench.json"
    _run_cli(
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
            "--out",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    result = _run_cli(
        [
            sys.executable,
            "-m",
            "vizcompress.cli",
            "recommend",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    summary = json.loads(result.stdout)
    assert summary["benchmark"] == str(output)
    assert "recommendation_counts" in summary["summary"]


def test_cli_inspect_vizasset(tmp_path):
    _run_cli(
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

    result = _run_cli(
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
    assert summary["retained"]["samples"] == 300
    assert summary["channel"]["samples"] == 300


def test_cli_build_can_write_review_packet(tmp_path):
    result = _run_cli(
        [
            sys.executable,
            "-m",
            "vizcompress.cli",
            "build",
            "--synthetic",
            "5000",
            "--fourier-terms",
            "96",
            "--package",
            "--direct-svg",
            "--review-packet",
            "--review-max-rmse",
            "0.003",
            "--review-max-error",
            "0.05",
            "--out",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    summary = json.loads(result.stdout)
    review_path = tmp_path / "model.vizretain" / "review.json"
    review = json.loads(review_path.read_text(encoding="utf-8"))
    assert str(review_path) in summary["outputs"]
    assert review["accepted"] is True
    assert review["source_fingerprint"]["sample_count"] == 5000
    assert review["baseline_evidence"]["direct_svg"]["present"] is True
    manifest = json.loads((tmp_path / "model.vizretain" / "asset.json").read_text(encoding="utf-8"))
    assert manifest["files"]["review"]["path"] == "review.json"
    assert len(manifest["files"]["review"]["sha256"]) == 64


def test_cli_build_can_require_review_pass(tmp_path):
    result = _run_cli(
        [
            sys.executable,
            "-m",
            "vizcompress.cli",
            "build",
            "--synthetic",
            "5000",
            "--fourier-terms",
            "96",
            "--package",
            "--review-packet",
            "--review-max-rmse",
            "0.000001",
            "--require-review-pass",
            "--out",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "review packet did not pass verification" in result.stderr


def test_cli_compare_reports_raw_and_gzip_baselines(tmp_path):
    _run_cli(
        [
            sys.executable,
            "-m",
            "vizcompress.cli",
            "build",
            "--synthetic",
            "5000",
            "--fourier-terms",
            "96",
            "--direct-svg",
            "--package",
            "--out",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    result = _run_cli(
        [
            sys.executable,
            "-m",
            "vizcompress.cli",
            "compare",
            str(tmp_path / "model.vizretain"),
            "--baseline",
            f"direct_svg={tmp_path / 'direct.svg'}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    summary = json.loads(result.stdout)
    direct = summary["baseline_evidence"]["direct_svg"]
    assert direct["present"] is True
    assert direct["bytes"] > 0
    assert direct["gzip_bytes"] > 0
    assert direct["gzip_to_package_ratio"] > 0.0


def test_terms_channel_sweep_summary_tracks_gate_win_counts():
    script_path = _repo_script("run_terms_channel_kind_threshold_sweep.py")
    spec = importlib.util.spec_from_file_location("run_terms_channel_kind_threshold_sweep", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load terms-channel sweep script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    synthetic_rows = [
        {
            "synthetic_kind": "smooth",
            "samples": 1000,
            "fourier_terms": 16,
            "direct_svg_to_package_ratio": 0.8,
            "direct_svg_gzip_to_package_ratio": 1.3,
            "source_csv_gzip_to_package_ratio": 1.1,
            "fourier_r2": 0.999,
            "channel_k": 3.0,
        },
        {
            "synthetic_kind": "steps",
            "samples": 2000,
            "fourier_terms": 16,
            "direct_svg_to_package_ratio": 0.9,
            "direct_svg_gzip_to_package_ratio": 0.5,
            "source_csv_gzip_to_package_ratio": 0.9,
            "fourier_r2": 0.999,
            "channel_k": 2.0,
            "channel_coverage_ratio": 0.95,
        },
    ]

    summary = module._summarize_rows(synthetic_rows, threshold=0.9)
    assert summary["package_wins_against_direct_svg_gzip_count"] == 1
    assert summary["package_wins_against_source_csv_gzip_count"] == 1
    assert summary["defensible_rows_count"] == 2
    assert summary["defensible_rows_ratio"] == 1.0

    gate = evaluate_benchmark_gate(
        {"rows": synthetic_rows, "summary": summary},
        require_svg_gzip_win=True,
        require_csv_gzip_win=True,
    )
    assert gate["ok"] is True

    failing_summary = dict(summary)
    failing_summary["package_wins_against_source_csv_gzip_count"] = 0
    gate = evaluate_benchmark_gate(
        {"rows": synthetic_rows, "summary": failing_summary},
        require_svg_gzip_win=True,
        require_csv_gzip_win=True,
    )
    assert gate["ok"] is False
    assert any("did not beat source CSV.gz" in error for error in gate["errors"])


def test_terms_channel_sweep_summary_handles_ratio_alias_and_string_ratio_values():
    script_path = _repo_script("run_terms_channel_kind_threshold_sweep.py")
    spec = importlib.util.spec_from_file_location("run_terms_channel_kind_threshold_sweep", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load terms-channel sweep script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    rows = [
        {
            "synthetic_kind": "smooth",
            "samples": 1000,
            "fourier_terms": 16,
            "direct_svg_to_package_ratio": "1.35",
            "fourier_r2": 0.999,
            "channel_k": 2.0,
            "source_csv_gzip_to_package_ratio": "0.8",
            "channel_coverage_ratio": "0.95",
        },
    ]

    summary = module._summarize_rows(rows, threshold=0.99)
    assert summary["best_direct_svg_gzip_to_package_ratio"] == 1.35
    assert summary["best_rows"]["direct_svg_gzip"]["ratio"] == 1.35
    summary_by_terms_k_key = "16|2.0" if "16|2.0" in summary["summary_by_terms_k"] else "16|2"
    assert summary["summary_by_terms_k"][summary_by_terms_k_key]["best_rows"]["direct_svg_gzip"]["ratio"] == 1.35


def test_terms_channel_grid_extract_best_row_prefers_numeric_ratio_string():
    script_path = _repo_script("run_terms_channel_grid_sweep.py")
    spec = importlib.util.spec_from_file_location("run_terms_channel_grid_sweep", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load terms-channel grid sweep script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    summary_by_terms_k = {
        "16|2.0": {"best_rows": {"direct_svg_gzip": {"ratio": "0.92", "samples": 1000}}},
        "32|2.0": {"best_rows": {"direct_svg_gzip": {"ratio": "1.10", "samples": 2000}}},
        "48|2.0": {"best_rows": {"direct_svg_gzip": {"ratio": "bad-value", "samples": 1500}}},
        "64|2.0": {"best_rows": {}},
    }
    key, row = module._extract_best_row(summary_by_terms_k, "ratio")
    assert key == "32|2.0"
    assert row["samples"] == 2000


def test_cli_inspect_reports_clean_profile_without_residual_layer(tmp_path):
    _run_cli(
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
    result = _run_cli(
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


def test_cli_inspect_reports_sparse_residual_details(tmp_path):
    _run_cli(
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
            "--out",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    result = _run_cli(
        [
            sys.executable,
            "-m",
            "vizcompress.cli",
            "inspect",
            str(tmp_path / "model.vizretain"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    summary = json.loads(result.stdout)
    assert summary["contains_sparse_residual_layer"] is True
    assert summary["sparse_residual"]["points"] > 0
    assert summary["retained"]["samples"] == 1200


def test_benchmark_gate_supports_defensible_ratio_and_high_fidelity_floor():
    result = benchmark_synthetic_terms_channel_k_sweep(
        [1200],
        fourier_terms_values=[16],
        channel_k_values=[2.0],
        synthetic_kind="smooth",
        rdp_epsilon=0.6,
        svg_samples=200,
        channel_window=16,
        channel_band_epsilon=0.04,
        smooth_window=1,
        sigma_clip=None,
        noise_layer_terms=0,
        auto_noise_layer=False,
        x_domain_policy="preserve",
        x_domain_epsilon=0.002,
        x_domain_max_error=1e-4,
    )

    high_fidelity_rows = result["summary"]["high_fidelity_rows_count"]
    pass_gate = evaluate_benchmark_gate(
        result,
        min_high_fidelity_rows=high_fidelity_rows,
        min_defensible_rows_ratio=0.0,
    )
    assert pass_gate["ok"] is True
    assert pass_gate["errors"] == []

    strict_gate = evaluate_benchmark_gate(
        result,
        min_high_fidelity_rows=high_fidelity_rows + 1,
        min_defensible_rows_ratio=0.0,
    )
    assert strict_gate["ok"] is False
    assert any("below minimum" in error for error in strict_gate["errors"])


def test_benchmark_gate_formats_channels_and_ratios():
    result = benchmark_synthetic_terms_channel_k_sweep(
        [800],
        fourier_terms_values=[16],
        channel_k_values=[2.0],
        synthetic_kind="smooth",
        rdp_epsilon=0.6,
        svg_samples=200,
        channel_window=16,
        channel_band_epsilon=0.04,
        smooth_window=1,
        sigma_clip=None,
        noise_layer_terms=0,
        auto_noise_layer=False,
        x_domain_policy="preserve",
        x_domain_epsilon=0.002,
        x_domain_max_error=1e-4,
    )

    gate = evaluate_benchmark_gate(
        result,
        min_defensible_rows_ratio=1.0,
    )
    assert gate["ok"] is False
    assert any("defensible ratio" in error for error in gate["errors"])

