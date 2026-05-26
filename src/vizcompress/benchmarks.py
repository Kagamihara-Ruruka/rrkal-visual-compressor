from __future__ import annotations

import json
import tempfile
import gzip
from pathlib import Path
from typing import Any

from vizcompress.analyzers import analyze_time_series
from vizcompress.cleaning import residual_time_series, sigma_clip_time_series, smooth_time_series
from vizcompress.compressors import compress_fourier, compress_fourier_channel, compress_rdp
from vizcompress.core import CompressionReport, TimeSeries
from vizcompress.data import SYNTHETIC_KINDS, make_synthetic_dataset
from vizcompress.domains import encode_x_domain
from vizcompress.exporters import path_from_xy, write_channel_svg, write_demo, write_fourier_svg, write_metrics, write_rdp_svg
from vizcompress.packages import write_vizasset
from vizcompress.residuals import analyze_residual, compress_sparse_residual
from vizcompress.selectors import count_recommendations, recommend_benchmark_row


def parse_sample_sizes(value: str) -> list[int]:
    sizes = [int(part.strip()) for part in value.split(",") if part.strip()]
    if not sizes:
        raise ValueError("at least one sample size is required")
    if any(size < 2 for size in sizes):
        raise ValueError("sample sizes must be >= 2")
    return sizes


def benchmark_synthetic_sizes(
    sample_sizes: list[int],
    *,
    synthetic_kind: str = "smooth",
    fourier_terms: int,
    rdp_epsilon: float,
    svg_samples: int,
    channel: bool,
    channel_k: float,
    channel_window: int,
    channel_band_epsilon: float,
    smooth_window: int = 1,
    sigma_clip: float | None = None,
    noise_layer_terms: int = 0,
    auto_noise_layer: bool = False,
    x_domain_policy: str = "preserve",
    x_domain_epsilon: float = 0.002,
    x_domain_max_error: float = 1e-4,
) -> dict[str, Any]:
    kinds = list(SYNTHETIC_KINDS) if synthetic_kind == "all" else [synthetic_kind]
    rows = [
        _benchmark_one(
            make_synthetic_dataset(size, kind=kind),
            synthetic_kind=kind,
            fourier_terms=fourier_terms,
            rdp_epsilon=rdp_epsilon,
            svg_samples=svg_samples,
            channel=channel,
            channel_k=channel_k,
            channel_window=channel_window,
            channel_band_epsilon=channel_band_epsilon,
            smooth_window=smooth_window,
            sigma_clip=sigma_clip,
            noise_layer_terms=noise_layer_terms,
            auto_noise_layer=auto_noise_layer,
            x_domain_policy=x_domain_policy,
            x_domain_epsilon=x_domain_epsilon,
            x_domain_max_error=x_domain_max_error,
        )
        for kind in kinds
        for size in sample_sizes
    ]
    return {
        "benchmark": "synthetic_size_sweep",
        "parameters": {
            "sample_sizes": sample_sizes,
            "synthetic_kind": synthetic_kind,
            "fourier_terms": fourier_terms,
            "rdp_epsilon": rdp_epsilon,
            "svg_samples": svg_samples,
            "channel": channel,
            "channel_k": channel_k,
            "channel_window": channel_window,
            "channel_band_epsilon": channel_band_epsilon,
            "smooth_window": smooth_window,
            "sigma_clip": sigma_clip,
            "noise_layer_terms": noise_layer_terms,
            "auto_noise_layer": auto_noise_layer,
            "x_domain_policy": x_domain_policy,
            "x_domain_epsilon": x_domain_epsilon,
            "x_domain_max_error": x_domain_max_error,
        },
        "summary": _summarize_rows(rows),
        "summary_by_kind": _summarize_rows_by_kind(rows),
        "rows": rows,
    }


def write_benchmark(path: str | Path, data: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return output


def _benchmark_one(
    series: TimeSeries,
    *,
    synthetic_kind: str,
    fourier_terms: int,
    rdp_epsilon: float,
    svg_samples: int,
    channel: bool,
    channel_k: float,
    channel_window: int,
    channel_band_epsilon: float,
    smooth_window: int,
    sigma_clip: float | None,
    noise_layer_terms: int,
    auto_noise_layer: bool,
    x_domain_policy: str,
    x_domain_epsilon: float,
    x_domain_max_error: float,
) -> dict[str, Any]:
    raw_series = series
    cleaning_steps = []
    if sigma_clip is not None:
        cleaning = sigma_clip_time_series(series, sigma_clip)
        cleaning_steps.append(cleaning.metadata())
        series = cleaning.cleaned
    if smooth_window > 1:
        cleaning = smooth_time_series(series, smooth_window)
        cleaning_steps.append(cleaning.metadata())
        series = cleaning.cleaned
    rdp = compress_rdp(series, rdp_epsilon)
    fourier = compress_fourier(series, fourier_terms)
    noise = None
    sparse_residual = None
    residual_profile = None
    if noise_layer_terms > 0 and cleaning_steps:
        residual = residual_time_series(raw_series, series)
        residual_profile = analyze_residual(raw_series, residual).as_dict()
        noise = compress_fourier(residual, noise_layer_terms)
    elif auto_noise_layer and cleaning_steps:
        residual = residual_time_series(raw_series, series)
        residual_profile = analyze_residual(raw_series, residual).as_dict()
        if residual_profile["recommended_strategy"] == "fourier_residual_layer":
            noise = compress_fourier(residual, max(16, fourier_terms // 2))
        elif residual_profile["recommended_strategy"] == "sparse_outlier_layer":
            sparse_residual = compress_sparse_residual(residual)
    channel_model = None
    if channel:
        channel_model = compress_fourier_channel(
            series,
            fourier_terms,
            window=channel_window,
            k=channel_k,
            band_epsilon=channel_band_epsilon,
        )
    profile = analyze_time_series(series).as_dict()
    if cleaning_steps:
        profile["cleaning"] = cleaning_steps
    x_domain = encode_x_domain(
        series,
        x_uniform=bool(profile["x_uniform"]),
        policy=x_domain_policy,
        epsilon=x_domain_epsilon,
        max_error=x_domain_max_error,
    )
    report = CompressionReport(
        series.sample_count,
        rdp,
        fourier,
        channel_model,
        profile,
        noise,
        sparse_residual,
        residual_profile,
    )
    direct_svg_bytes = _estimate_direct_svg_bytes(series)
    direct_svg_gzip_bytes = _estimate_direct_svg_gzip_bytes(series)
    with tempfile.TemporaryDirectory(prefix="vizcompress-bench-") as temp:
        temp_dir = Path(temp)
        rdp_svg = write_rdp_svg(temp_dir / "rdp_vectorized.svg", series, rdp)
        fourier_svg = write_fourier_svg(temp_dir / "fourier_vectorized.svg", series, fourier, svg_samples)
        preview = fourier_svg
        generated = [rdp_svg.name, fourier_svg.name]
        if channel_model is not None:
            channel_svg = write_channel_svg(temp_dir / "fourier_channel.svg", series, channel_model, svg_samples)
            preview = channel_svg
            generated.append(channel_svg.name)
        demo = write_demo(temp_dir / "demo.py", series.sample_count, fourier_terms)
        metrics = write_metrics(temp_dir / "metrics.json", report, [*generated, demo.name, "metrics.json"])
        package = write_vizasset(
            temp_dir / "model.vizretain",
            series=series,
            report=report,
            preview_svg=preview,
            metrics_json=metrics,
            demo_py=demo,
            package_profile="retain-residual",
            x_domain_policy=x_domain_policy,
            x_domain_epsilon=x_domain_epsilon,
            x_domain_max_error=x_domain_max_error,
        )
        package_bytes = _directory_size(package)
        model_bytes = (package / "model.npz").stat().st_size
        preview_bytes = (package / "preview.svg").stat().st_size

    ratio = direct_svg_bytes / float(package_bytes) if package_bytes else 0.0
    gzip_ratio = direct_svg_gzip_bytes / float(package_bytes) if package_bytes else 0.0
    row = {
        "synthetic_kind": synthetic_kind,
        "samples": series.sample_count,
        "x_uniform": bool(report.as_dict()["input"]["x_uniform"]),
        "x_domain_mode": x_domain.mode,
        "x_domain_parameter_count": x_domain.metrics["parameter_count"],
        "x_domain_max_abs_error": x_domain.metrics["max_abs_error"],
        "x_domain_rmse": x_domain.metrics["rmse"],
        "cleaning": cleaning_steps or None,
        "direct_svg_bytes": direct_svg_bytes,
        "direct_svg_gzip_bytes": direct_svg_gzip_bytes,
        "package_bytes": package_bytes,
        "model_npz_bytes": model_bytes,
        "preview_svg_bytes": preview_bytes,
        "direct_svg_to_package_ratio": ratio,
        "direct_svg_gzip_to_package_ratio": gzip_ratio,
        "fourier_parameter_count": fourier.parameter_count,
        "rdp_parameter_count": rdp.parameter_count,
        "channel_parameter_count": channel_model.parameter_count if channel_model is not None else None,
        "noise_parameter_count": noise.parameter_count if noise is not None else None,
        "sparse_residual_parameter_count": sparse_residual.parameter_count if sparse_residual is not None else None,
        "fourier_r2": fourier.metrics["r2"],
        "noise_r2": noise.metrics["r2"] if noise is not None else None,
        "residual_strategy": residual_profile["recommended_strategy"] if residual_profile is not None else None,
        "residual_spectral_concentration": (
            residual_profile["spectral_concentration"] if residual_profile is not None else None
        ),
        "channel_coverage_ratio": channel_model.coverage_ratio if channel_model is not None else None,
    }
    row["recommendation"] = recommend_benchmark_row(row)
    return row


def _estimate_direct_svg_bytes(series: TimeSeries) -> int:
    return len(_direct_svg_document(series).encode("utf-8"))


def _estimate_direct_svg_gzip_bytes(series: TimeSeries) -> int:
    return len(gzip.compress(_direct_svg_document(series).encode("utf-8"), compresslevel=9, mtime=0))


def _direct_svg_document(series: TimeSeries) -> str:
    path = path_from_xy(series.x, series.y)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="420" viewBox="0 0 1200 420">'
        '<rect width="100%" height="100%" fill="#fbfbf8"/>'
        f'<path d="{path}" fill="none" stroke="#111" stroke-width="2"/>'
        "</svg>"
    )


def _directory_size(path: Path) -> int:
    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    winning_rows = [row for row in rows if row["direct_svg_to_package_ratio"] > 1.0]
    best_row = max(rows, key=lambda row: row["direct_svg_to_package_ratio"])
    return {
        "observed_break_even_samples": winning_rows[0]["samples"] if winning_rows else None,
        "best_ratio_samples": best_row["samples"],
        "best_direct_svg_to_package_ratio": best_row["direct_svg_to_package_ratio"],
        "package_wins_count": len(winning_rows),
        "direct_svg_wins_count": len(rows) - len(winning_rows),
        "recommendation_counts": count_recommendations(rows),
    }


def _summarize_rows_by_kind(rows: list[dict[str, Any]]) -> dict[str, Any]:
    kinds = sorted({str(row["synthetic_kind"]) for row in rows})
    return {
        kind: _summarize_rows([row for row in rows if row["synthetic_kind"] == kind])
        for kind in kinds
    }
