from __future__ import annotations

import json
import subprocess
import sys

import numpy as np

from vizcompress.analyzers import analyze_time_series
from vizcompress.benchmarks import benchmark_synthetic_sizes, parse_sample_sizes
from vizcompress.cleaning import residual_time_series, sigma_clip_time_series, smooth_time_series
from vizcompress.compressors import compress_fourier, compress_fourier_channel, compress_lttb, compress_rdp, lttb_indices
from vizcompress.core import CompressionReport
from vizcompress.data import SYNTHETIC_KINDS, make_synthetic_dataset, make_synthetic_signal, read_csv_timeseries
from vizcompress.exporters import write_channel_svg, write_demo, write_direct_svg, write_fourier_svg, write_metrics, write_rdp_svg
from vizcompress.packages import (
    load_vizasset_manifest,
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
    assert len(result["rows"]) == 2
    assert result["rows"][1]["direct_svg_bytes"] > result["rows"][0]["direct_svg_bytes"]
    assert result["rows"][1]["direct_svg_gzip_bytes"] > result["rows"][0]["direct_svg_gzip_bytes"]
    assert result["rows"][1]["source_csv_bytes"] > result["rows"][0]["source_csv_bytes"]
    assert result["rows"][1]["source_csv_gzip_bytes"] > result["rows"][0]["source_csv_gzip_bytes"]
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
    assert "gzip_recommendation_counts" in result["summary"]


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


def test_cli_recommend_reads_benchmark_json(tmp_path):
    output = tmp_path / "bench.json"
    subprocess.run(
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

    result = subprocess.run(
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
    assert summary["retained"]["samples"] == 300
    assert summary["channel"]["samples"] == 300


def test_cli_build_can_write_review_packet(tmp_path):
    result = subprocess.run(
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


def test_cli_build_can_require_review_pass(tmp_path):
    result = subprocess.run(
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
    subprocess.run(
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

    result = subprocess.run(
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


def test_cli_inspect_reports_sparse_residual_details(tmp_path):
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
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    summary = json.loads(result.stdout)
    assert summary["contains_sparse_residual_layer"] is True
    assert summary["sparse_residual"]["points"] > 0
    assert summary["retained"]["samples"] == 1200
