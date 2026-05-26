from __future__ import annotations

import json
import tempfile
import gzip
from pathlib import Path
from typing import Any

from vizcompress.analyzers import analyze_time_series
from vizcompress.cleaning import residual_time_series, sigma_clip_time_series, smooth_time_series
from vizcompress.compressors import compress_fourier, compress_fourier_channel, compress_lttb, compress_rdp
from vizcompress.core import CompressionReport, TimeSeries
from vizcompress.data import SYNTHETIC_KINDS, make_synthetic_dataset
from vizcompress.domains import encode_x_domain
from vizcompress.exporters import path_from_xy, write_channel_svg, write_demo, write_fourier_svg, write_metrics, write_rdp_svg
from vizcompress.packages import write_vizasset
from vizcompress.residuals import analyze_residual, compress_sparse_residual
from vizcompress.selectors import count_recommendations, recommend_benchmark_row, recommend_benchmark_row_gzip


def parse_sample_sizes(value: str) -> list[int]:
    sizes = _parse_positive_int_list(value, name="sample sizes", minimum=2)
    if not sizes:
        raise ValueError("at least one sample size is required")
    return sizes


def parse_fourier_terms(value: str) -> list[int]:
    return _parse_positive_int_list(value, name="fourier terms", minimum=1)


def parse_float_values(value: str, *, name: str, minimum: float | None = None) -> list[float]:
    values = [float(part.strip()) for part in value.split(",") if part.strip()]
    if not values:
        raise ValueError(f"at least one {name} value is required")
    if minimum is not None and any(item < minimum for item in values):
        raise ValueError(f"{name} values must be >= {minimum}")
    return values


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


def benchmark_synthetic_fourier_terms(
    sample_sizes: list[int],
    *,
    fourier_terms_values: list[int],
    synthetic_kind: str = "smooth",
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
    rows = []
    for terms in fourier_terms_values:
        data = benchmark_synthetic_sizes(
            sample_sizes,
            synthetic_kind=synthetic_kind,
            fourier_terms=terms,
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
        for row in data["rows"]:
            row["fourier_terms"] = terms
            rows.append(row)
    return {
        "benchmark": "synthetic_fourier_terms_sweep",
        "parameters": {
            "sample_sizes": sample_sizes,
            "synthetic_kind": synthetic_kind,
            "fourier_terms_values": fourier_terms_values,
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
        "summary_by_terms": _summarize_rows_by_terms(rows),
        "rows": rows,
    }


def benchmark_synthetic_channel_k(
    sample_sizes: list[int],
    *,
    channel_k_values: list[float],
    synthetic_kind: str = "smooth",
    fourier_terms: int,
    rdp_epsilon: float,
    svg_samples: int,
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
    rows = []
    for k_value in channel_k_values:
        data = benchmark_synthetic_sizes(
            sample_sizes,
            synthetic_kind=synthetic_kind,
            fourier_terms=fourier_terms,
            rdp_epsilon=rdp_epsilon,
            svg_samples=svg_samples,
            channel=True,
            channel_k=k_value,
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
        for row in data["rows"]:
            row["channel_k"] = k_value
            rows.append(row)
    return {
        "benchmark": "synthetic_channel_k_sweep",
        "parameters": {
            "sample_sizes": sample_sizes,
            "synthetic_kind": synthetic_kind,
            "fourier_terms": fourier_terms,
            "channel_k_values": channel_k_values,
            "rdp_epsilon": rdp_epsilon,
            "svg_samples": svg_samples,
            "channel": True,
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
        "summary_by_channel_k": _summarize_rows_by_channel_k(rows),
        "rows": rows,
    }


def write_benchmark(path: str | Path, data: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return output


def write_benchmark_markdown(path: str | Path, data: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(format_benchmark_markdown(data), encoding="utf-8")
    return output


def format_benchmark_markdown(data: dict[str, Any]) -> str:
    parameters = data.get("parameters", {})
    summary = data.get("summary", {})
    rows = data.get("rows", [])
    lines = [
        "# VizCompress Benchmark Report",
        "",
        "## Parameters",
        "",
        f"- Synthetic kind: `{parameters.get('synthetic_kind', 'unknown')}`",
        f"- Sample sizes: `{parameters.get('sample_sizes', [])}`",
        f"- Fourier terms: `{parameters.get('fourier_terms', parameters.get('fourier_terms_values', 'unknown'))}`",
        f"- Channel K values: `{parameters.get('channel_k_values', parameters.get('channel_k', 'n/a'))}`",
        f"- SVG samples: `{parameters.get('svg_samples', 'unknown')}`",
        f"- Channel model: `{parameters.get('channel', False)}`",
        f"- X-domain policy: `{parameters.get('x_domain_policy', 'unknown')}`",
        "",
        "## Summary",
        "",
        f"- Raw SVG break-even samples: `{summary.get('observed_break_even_samples')}`",
        f"- Best raw SVG/package ratio: `{_format_float(summary.get('best_direct_svg_to_package_ratio'))}`",
        f"- Best SVG.gz/package ratio: `{_format_float(summary.get('best_direct_svg_gzip_to_package_ratio'))}`",
        f"- Best CSV.gz/package ratio: `{_format_float(summary.get('best_source_csv_gzip_to_package_ratio'))}`",
        f"- Best high-fidelity SVG.gz candidate: `{_format_candidate(summary.get('best_high_fidelity_svg_gzip_candidate'))}`",
        f"- Package wins against SVG.gz: `{summary.get('package_wins_against_direct_svg_gzip_count', 0)}`",
        f"- Package wins against CSV.gz: `{summary.get('package_wins_against_source_csv_gzip_count', 0)}`",
        "",
        "## Rows",
        "",
        "| kind | samples | terms | channel K | package bytes | SVG.gz/package | CSV.gz/package | LTTB SVG.gz/package | Fourier R2 | LTTB R2 | coverage | gzip recommendation |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("synthetic_kind", "")),
                    str(row.get("samples", "")),
                    str(row.get("fourier_terms", "")),
                    _format_float(row.get("channel_k")),
                    str(row.get("package_bytes", "")),
                    _format_float(row.get("direct_svg_gzip_to_package_ratio")),
                    _format_float(row.get("source_csv_gzip_to_package_ratio")),
                    _format_float(row.get("lttb_svg_gzip_to_package_ratio")),
                    _format_float(row.get("fourier_r2")),
                    _format_float(row.get("lttb_r2")),
                    _format_float(row.get("channel_coverage_ratio")),
                    str(row.get("gzip_recommendation", "")),
                ]
            )
            + " |"
        )
    gate = data.get("benchmark_gate")
    if isinstance(gate, dict):
        lines.extend(
            [
                "",
                "## Benchmark Gate",
                "",
                f"- OK: `{gate.get('ok')}`",
                f"- Policy: `{gate.get('policy', {})}`",
                f"- Errors: `{gate.get('errors', [])}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- A ratio above `1.0` means the model package is smaller than that baseline.",
            "- LTTB is a downsampling baseline, not a package format; its SVG ratio estimates the size after exporting sampled points as a path.",
            "- Higher R2 alone is not enough. The package must also pass source verification and size evidence checks.",
            "",
        ]
    )
    return "\n".join(lines)


def evaluate_benchmark_gate(
    data: dict[str, Any],
    *,
    require_svg_gzip_win: bool = False,
    require_csv_gzip_win: bool = False,
    min_fourier_r2: float | None = None,
    min_channel_coverage: float | None = None,
) -> dict[str, Any]:
    rows = data.get("rows", [])
    summary = data.get("summary", {})
    errors = []
    if require_svg_gzip_win and int(summary.get("package_wins_against_direct_svg_gzip_count", 0)) < 1:
        errors.append("package did not beat SVG.gz in any benchmark row")
    if require_csv_gzip_win and int(summary.get("package_wins_against_source_csv_gzip_count", 0)) < 1:
        errors.append("package did not beat source CSV.gz in any benchmark row")
    if min_fourier_r2 is not None:
        weak_rows = [
            {"synthetic_kind": row.get("synthetic_kind"), "samples": row.get("samples"), "fourier_r2": row.get("fourier_r2")}
            for row in rows
            if float(row.get("fourier_r2", 0.0)) < min_fourier_r2
        ]
        if weak_rows:
            errors.append(f"{len(weak_rows)} row(s) below min Fourier R2 {min_fourier_r2}")
    if min_channel_coverage is not None:
        weak_channel_rows = [
            {
                "synthetic_kind": row.get("synthetic_kind"),
                "samples": row.get("samples"),
                "fourier_terms": row.get("fourier_terms"),
                "channel_coverage_ratio": row.get("channel_coverage_ratio"),
            }
            for row in rows
            if row.get("channel_coverage_ratio") is None
            or float(row.get("channel_coverage_ratio", 0.0)) < min_channel_coverage
        ]
        if weak_channel_rows:
            errors.append(f"{len(weak_channel_rows)} row(s) below min channel coverage {min_channel_coverage}")
    return {
        "ok": not errors,
        "errors": errors,
        "policy": {
            "require_svg_gzip_win": require_svg_gzip_win,
            "require_csv_gzip_win": require_csv_gzip_win,
            "min_fourier_r2": min_fourier_r2,
            "min_channel_coverage": min_channel_coverage,
        },
    }


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
    lttb = compress_lttb(series, min(svg_samples, series.sample_count))
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
    source_csv_bytes = _estimate_source_csv_bytes(series)
    source_csv_gzip_bytes = _estimate_source_csv_gzip_bytes(series)
    lttb_series = TimeSeries(x=lttb.x, y=lttb.y, source=f"lttb:{series.source}")
    lttb_svg_bytes = _estimate_direct_svg_bytes(lttb_series)
    lttb_svg_gzip_bytes = _estimate_direct_svg_gzip_bytes(lttb_series)
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
    csv_ratio = source_csv_bytes / float(package_bytes) if package_bytes else 0.0
    csv_gzip_ratio = source_csv_gzip_bytes / float(package_bytes) if package_bytes else 0.0
    lttb_svg_ratio = lttb_svg_bytes / float(package_bytes) if package_bytes else 0.0
    lttb_svg_gzip_ratio = lttb_svg_gzip_bytes / float(package_bytes) if package_bytes else 0.0
    row = {
        "synthetic_kind": synthetic_kind,
        "samples": series.sample_count,
        "fourier_terms": fourier_terms,
        "channel_k": channel_k if channel_model is not None else None,
        "x_uniform": bool(report.as_dict()["input"]["x_uniform"]),
        "x_domain_mode": x_domain.mode,
        "x_domain_parameter_count": x_domain.metrics["parameter_count"],
        "x_domain_max_abs_error": x_domain.metrics["max_abs_error"],
        "x_domain_rmse": x_domain.metrics["rmse"],
        "cleaning": cleaning_steps or None,
        "direct_svg_bytes": direct_svg_bytes,
        "direct_svg_gzip_bytes": direct_svg_gzip_bytes,
        "source_csv_bytes": source_csv_bytes,
        "source_csv_gzip_bytes": source_csv_gzip_bytes,
        "lttb_svg_bytes": lttb_svg_bytes,
        "lttb_svg_gzip_bytes": lttb_svg_gzip_bytes,
        "package_bytes": package_bytes,
        "model_npz_bytes": model_bytes,
        "preview_svg_bytes": preview_bytes,
        "direct_svg_to_package_ratio": ratio,
        "direct_svg_gzip_to_package_ratio": gzip_ratio,
        "source_csv_to_package_ratio": csv_ratio,
        "source_csv_gzip_to_package_ratio": csv_gzip_ratio,
        "lttb_svg_to_package_ratio": lttb_svg_ratio,
        "lttb_svg_gzip_to_package_ratio": lttb_svg_gzip_ratio,
        "fourier_parameter_count": fourier.parameter_count,
        "rdp_parameter_count": rdp.parameter_count,
        "lttb_parameter_count": lttb.parameter_count,
        "channel_parameter_count": channel_model.parameter_count if channel_model is not None else None,
        "noise_parameter_count": noise.parameter_count if noise is not None else None,
        "sparse_residual_parameter_count": sparse_residual.parameter_count if sparse_residual is not None else None,
        "fourier_r2": fourier.metrics["r2"],
        "lttb_r2": lttb.metrics["r2"],
        "lttb_rmse": lttb.metrics["rmse"],
        "noise_r2": noise.metrics["r2"] if noise is not None else None,
        "residual_strategy": residual_profile["recommended_strategy"] if residual_profile is not None else None,
        "residual_spectral_concentration": (
            residual_profile["spectral_concentration"] if residual_profile is not None else None
        ),
        "channel_coverage_ratio": channel_model.coverage_ratio if channel_model is not None else None,
    }
    row["recommendation"] = recommend_benchmark_row(row)
    row["gzip_recommendation"] = recommend_benchmark_row_gzip(row)
    return row


def _estimate_direct_svg_bytes(series: TimeSeries) -> int:
    return len(_direct_svg_document(series).encode("utf-8"))


def _estimate_direct_svg_gzip_bytes(series: TimeSeries) -> int:
    return len(gzip.compress(_direct_svg_document(series).encode("utf-8"), compresslevel=9, mtime=0))


def _estimate_source_csv_bytes(series: TimeSeries) -> int:
    return len(_source_csv_document(series).encode("utf-8"))


def _estimate_source_csv_gzip_bytes(series: TimeSeries) -> int:
    return len(gzip.compress(_source_csv_document(series).encode("utf-8"), compresslevel=9, mtime=0))


def _direct_svg_document(series: TimeSeries) -> str:
    path = path_from_xy(series.x, series.y)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="420" viewBox="0 0 1200 420">'
        '<rect width="100%" height="100%" fill="#fbfbf8"/>'
        f'<path d="{path}" fill="none" stroke="#111" stroke-width="2"/>'
        "</svg>"
    )


def _source_csv_document(series: TimeSeries) -> str:
    lines = ["time,value"]
    lines.extend(f"{float(x):.17g},{float(y):.17g}" for x, y in zip(series.x, series.y))
    return "\n".join(lines) + "\n"


def _directory_size(path: Path) -> int:
    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())


def _format_float(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return f"{float(value):.6g}"
    return str(value)


def _format_candidate(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return (
        f"{value.get('synthetic_kind')} / {value.get('samples')} samples / "
        f"{value.get('fourier_terms')} terms / "
        f"{value.get('ratio_field')}={_format_float(value.get('ratio'))} / "
        f"R2={_format_float(value.get('fourier_r2'))} / "
        f"{value.get('gzip_recommendation')}"
    )


def _parse_positive_int_list(value: str, *, name: str, minimum: int) -> list[int]:
    values = [int(part.strip()) for part in value.split(",") if part.strip()]
    if not values:
        raise ValueError(f"at least one {name} value is required")
    if any(item < minimum for item in values):
        raise ValueError(f"{name} values must be >= {minimum}")
    return values


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    winning_rows = [row for row in rows if row["direct_svg_to_package_ratio"] > 1.0]
    best_row = max(rows, key=lambda row: row["direct_svg_to_package_ratio"])
    gzip_winning_rows = [row for row in rows if row["direct_svg_gzip_to_package_ratio"] > 1.0]
    csv_gzip_winning_rows = [row for row in rows if row["source_csv_gzip_to_package_ratio"] > 1.0]
    best_gzip_row = max(rows, key=lambda row: row["direct_svg_gzip_to_package_ratio"])
    best_csv_gzip_row = max(rows, key=lambda row: row["source_csv_gzip_to_package_ratio"])
    high_fidelity_rows = [row for row in rows if row["fourier_r2"] >= 0.99]
    best_high_fidelity_svg_gzip = _best_row(high_fidelity_rows, "direct_svg_gzip_to_package_ratio")
    best_high_fidelity_csv_gzip = _best_row(high_fidelity_rows, "source_csv_gzip_to_package_ratio")
    return {
        "observed_break_even_samples": winning_rows[0]["samples"] if winning_rows else None,
        "best_ratio_samples": best_row["samples"],
        "best_direct_svg_to_package_ratio": best_row["direct_svg_to_package_ratio"],
        "best_direct_svg_gzip_ratio_samples": best_gzip_row["samples"],
        "best_direct_svg_gzip_to_package_ratio": best_gzip_row["direct_svg_gzip_to_package_ratio"],
        "best_source_csv_gzip_ratio_samples": best_csv_gzip_row["samples"],
        "best_source_csv_gzip_to_package_ratio": best_csv_gzip_row["source_csv_gzip_to_package_ratio"],
        "package_wins_count": len(winning_rows),
        "direct_svg_wins_count": len(rows) - len(winning_rows),
        "package_wins_against_direct_svg_gzip_count": len(gzip_winning_rows),
        "direct_svg_gzip_wins_count": len(rows) - len(gzip_winning_rows),
        "package_wins_against_source_csv_gzip_count": len(csv_gzip_winning_rows),
        "source_csv_gzip_wins_count": len(rows) - len(csv_gzip_winning_rows),
        "best_rows": {
            "direct_svg": _row_identity(best_row, ratio_field="direct_svg_to_package_ratio"),
            "direct_svg_gzip": _row_identity(best_gzip_row, ratio_field="direct_svg_gzip_to_package_ratio"),
            "source_csv_gzip": _row_identity(best_csv_gzip_row, ratio_field="source_csv_gzip_to_package_ratio"),
        },
        "high_fidelity_threshold_r2": 0.99,
        "best_high_fidelity_svg_gzip_candidate": (
            _row_identity(best_high_fidelity_svg_gzip, ratio_field="direct_svg_gzip_to_package_ratio")
            if best_high_fidelity_svg_gzip is not None
            else None
        ),
        "best_high_fidelity_csv_gzip_candidate": (
            _row_identity(best_high_fidelity_csv_gzip, ratio_field="source_csv_gzip_to_package_ratio")
            if best_high_fidelity_csv_gzip is not None
            else None
        ),
        "recommendation_counts": count_recommendations(rows),
        "gzip_recommendation_counts": count_recommendations(rows, field="gzip_recommendation"),
    }


def _best_row(rows: list[dict[str, Any]], ratio_field: str) -> dict[str, Any] | None:
    if not rows:
        return None
    return max(rows, key=lambda row: row[ratio_field])


def _row_identity(row: dict[str, Any], *, ratio_field: str) -> dict[str, Any]:
    return {
        "synthetic_kind": row["synthetic_kind"],
        "samples": row["samples"],
        "fourier_terms": row["fourier_terms"],
        "package_bytes": row["package_bytes"],
        "ratio_field": ratio_field,
        "ratio": row[ratio_field],
        "fourier_r2": row["fourier_r2"],
        "lttb_r2": row["lttb_r2"],
        "gzip_recommendation": row["gzip_recommendation"],
    }


def _summarize_rows_by_kind(rows: list[dict[str, Any]]) -> dict[str, Any]:
    kinds = sorted({str(row["synthetic_kind"]) for row in rows})
    return {
        kind: _summarize_rows([row for row in rows if row["synthetic_kind"] == kind])
        for kind in kinds
    }


def _summarize_rows_by_terms(rows: list[dict[str, Any]]) -> dict[str, Any]:
    terms = sorted({int(row["fourier_terms"]) for row in rows})
    return {
        str(term): _summarize_rows([row for row in rows if int(row["fourier_terms"]) == term])
        for term in terms
    }


def _summarize_rows_by_channel_k(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = sorted({float(row["channel_k"]) for row in rows if row.get("channel_k") is not None})
    return {
        _format_float(value): _summarize_rows([row for row in rows if row.get("channel_k") == value])
        for value in values
    }
