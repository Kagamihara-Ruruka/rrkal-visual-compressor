from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from vizcompress.analyzers import analyze_time_series
from vizcompress.compressors import compress_fourier, compress_fourier_channel, compress_rdp
from vizcompress.core import CompressionReport, TimeSeries
from vizcompress.data import make_synthetic_signal
from vizcompress.exporters import path_from_xy, write_channel_svg, write_demo, write_fourier_svg, write_metrics, write_rdp_svg
from vizcompress.packages import write_vizasset


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
    fourier_terms: int,
    rdp_epsilon: float,
    svg_samples: int,
    channel: bool,
    channel_k: float,
    channel_window: int,
    channel_band_epsilon: float,
) -> dict[str, Any]:
    rows = [
        _benchmark_one(
            make_synthetic_signal(size),
            fourier_terms=fourier_terms,
            rdp_epsilon=rdp_epsilon,
            svg_samples=svg_samples,
            channel=channel,
            channel_k=channel_k,
            channel_window=channel_window,
            channel_band_epsilon=channel_band_epsilon,
        )
        for size in sample_sizes
    ]
    return {
        "benchmark": "synthetic_size_sweep",
        "parameters": {
            "sample_sizes": sample_sizes,
            "fourier_terms": fourier_terms,
            "rdp_epsilon": rdp_epsilon,
            "svg_samples": svg_samples,
            "channel": channel,
            "channel_k": channel_k,
            "channel_window": channel_window,
            "channel_band_epsilon": channel_band_epsilon,
        },
        "summary": _summarize_rows(rows),
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
    fourier_terms: int,
    rdp_epsilon: float,
    svg_samples: int,
    channel: bool,
    channel_k: float,
    channel_window: int,
    channel_band_epsilon: float,
) -> dict[str, Any]:
    rdp = compress_rdp(series, rdp_epsilon)
    fourier = compress_fourier(series, fourier_terms)
    channel_model = None
    if channel:
        channel_model = compress_fourier_channel(
            series,
            fourier_terms,
            window=channel_window,
            k=channel_k,
            band_epsilon=channel_band_epsilon,
        )
    report = CompressionReport(series.sample_count, rdp, fourier, channel_model, analyze_time_series(series).as_dict())
    direct_svg_bytes = _estimate_direct_svg_bytes(series)
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
            temp_dir / "model.vizasset",
            series=series,
            report=report,
            preview_svg=preview,
            metrics_json=metrics,
            demo_py=demo,
        )
        package_bytes = _directory_size(package)
        model_bytes = (package / "model.npz").stat().st_size
        preview_bytes = (package / "preview.svg").stat().st_size

    ratio = direct_svg_bytes / float(package_bytes) if package_bytes else 0.0
    return {
        "samples": series.sample_count,
        "x_uniform": bool(report.as_dict()["input"]["x_uniform"]),
        "direct_svg_bytes": direct_svg_bytes,
        "package_bytes": package_bytes,
        "model_npz_bytes": model_bytes,
        "preview_svg_bytes": preview_bytes,
        "direct_svg_to_package_ratio": ratio,
        "fourier_parameter_count": fourier.parameter_count,
        "rdp_parameter_count": rdp.parameter_count,
        "channel_parameter_count": channel_model.parameter_count if channel_model is not None else None,
        "fourier_r2": fourier.metrics["r2"],
        "channel_coverage_ratio": channel_model.coverage_ratio if channel_model is not None else None,
    }


def _estimate_direct_svg_bytes(series: TimeSeries) -> int:
    path = path_from_xy(series.x, series.y)
    document = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="420" viewBox="0 0 1200 420">'
        '<rect width="100%" height="100%" fill="#fbfbf8"/>'
        f'<path d="{path}" fill="none" stroke="#111" stroke-width="2"/>'
        "</svg>"
    )
    return len(document.encode("utf-8"))


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
    }
