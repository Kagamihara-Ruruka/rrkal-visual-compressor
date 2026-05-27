from __future__ import annotations

"""Benchmark helpers for the video functional compression prototype."""

from pathlib import Path
import json
from typing import Any

from vizcompress.video import (
    compress_video,
    estimate_video_model_ratio,
    make_synthetic_video,
)


def parse_int_list(value: str, *, minimum: int) -> list[int]:
    values = [int(part.strip()) for part in value.split(",") if part.strip()]
    if not values:
        raise ValueError("at least one value is required")
    if any(item < minimum for item in values):
        raise ValueError(f"all values must be >= {minimum}")
    return values


def benchmark_video_sweep(
    frame_counts: list[int],
    *,
    height: int,
    width: int,
    rank_values: list[int],
    temporal_terms_values: list[int],
    noise_sigma: float = 0.0,
    baseline_noise_std: float = 0.0,
) -> dict[str, Any]:
    """Run a grid sweep over frames x rank x terms with evidence rows."""
    rows = []
    for frame_count in frame_counts:
        if frame_count < 2:
            continue
        for rank in rank_values:
            for terms in temporal_terms_values:
                row = benchmark_one_video_config(
                    frame_count=frame_count,
                    height=height,
                    width=width,
                    rank=rank,
                    temporal_terms=terms,
                    noise_sigma=noise_sigma,
                    baseline_noise_std=baseline_noise_std,
                )
                rows.append(row)
    summary = _summarize_rows(rows)
    return {
        "benchmark": "video_bench_sweep",
        "parameters": {
            "frame_counts": frame_counts,
            "height": height,
            "width": width,
            "rank_values": rank_values,
            "temporal_terms_values": temporal_terms_values,
            "noise_sigma": noise_sigma,
            "baseline_noise_std": baseline_noise_std,
        },
        "rows": rows,
        "summary": summary,
    }


def benchmark_one_video_config(
    *,
    frame_count: int,
    height: int,
    width: int,
    rank: int,
    temporal_terms: int,
    noise_sigma: float = 0.0,
    baseline_noise_std: float = 0.0,
) -> dict[str, Any]:
    source = make_synthetic_video(
        frame_count,
        height=height,
        width=width,
        noise_sigma=noise_sigma,
        source=f"synthetic-video:{frame_count}:{height}x{width}:r{rank}:t{temporal_terms}",
    )
    model = compress_video(source, rank=rank, temporal_terms=temporal_terms)
    evidence = estimate_video_model_ratio(source, model, samples=frame_count)

    baseline_metrics = _pixel_scale_reference(source, baseline_noise_std=baseline_noise_std)
    return {
        "frame_count": frame_count,
        "height": int(height),
        "width": int(width),
        "rank": rank,
        "temporal_terms": temporal_terms,
        "model_parameter_count": int(model.parameter_count),
        "raw_video_bytes": int(evidence["raw_video_bytes"]),
        "model_bytes": int(evidence["model_bytes"]),
        "compression_ratio": float(evidence["compression_ratio"]),
        "rmse": float(evidence["recon_metrics"]["rmse"]),
        "mae": float(evidence["recon_metrics"]["mae"]),
        "max_abs": float(evidence["recon_metrics"]["max_abs"]),
        "r2": float(evidence["recon_metrics"]["r2"]),
        "baseline_r2": float(baseline_metrics["r2"]),
        "baseline_rmse": float(baseline_metrics["rmse"]),
        "beats_raw_bytes": int(evidence["model_bytes"] < baseline_metrics["raw_bytes"]),
        "beats_noisy_raw_bytes": int(evidence["model_bytes"] < baseline_metrics["noisy_raw_bytes"]),
    }


def format_video_benchmark_markdown(data: dict[str, Any]) -> str:
    parameters = data.get("parameters", {})
    summary = data.get("summary", {})
    lines = [
        "# Video Functional Compression Benchmarks",
        "",
        "## Parameters",
        f"- Frame counts: `{parameters.get('frame_counts', [])}`",
        f"- Spatial size: `{parameters.get('height', 'n/a')}x{parameters.get('width', 'n/a')}`",
        f"- Rank sweep: `{parameters.get('rank_values', [])}`",
        f"- Temporal term sweep: `{parameters.get('temporal_terms_values', [])}`",
        f"- Noise sigma: `{parameters.get('noise_sigma', 0.0)}`",
        "",
        "## Summary",
        f"- Best compression ratio: `{_format_float(summary.get('best_compression_ratio'))}`",
        f"- Best R2: `{_format_float(summary.get('best_r2'))}`",
        f"- Rows: `{summary.get('row_count', 0)}`",
        f"- Beats raw bytes: `{summary.get('beats_raw_bytes_count', 0)}`",
        f"- Best row: `{_format_candidate(summary.get('best_row'))}`",
        "",
        "## Rows",
        "| frames | rank | temporal_terms | compression_ratio | r2 | RMSE | model_bytes | raw_bytes |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in data.get("rows", []):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("frame_count", "")),
                    str(row.get("rank", "")),
                    str(row.get("temporal_terms", "")),
                    _format_float(row.get("compression_ratio")),
                    _format_float(row.get("r2")),
                    _format_float(row.get("rmse")),
                    str(row.get("model_bytes", "")),
                    str(row.get("raw_video_bytes", "")),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def write_video_benchmark(path: str | Path, data: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return output


def write_video_benchmark_markdown(path: str | Path, data: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(format_video_benchmark_markdown(data), encoding="utf-8")
    return output


def _pixel_scale_reference(video, *, baseline_noise_std: float = 0.0) -> dict[str, float]:
    base = {
        "raw_bytes": int(video.frames.nbytes),
        "noisy_raw_bytes": int(video.frames.nbytes),
        "rmse": 0.0,
        "mae": 0.0,
        "max_abs": 0.0,
        "r2": 1.0,
    }
    if baseline_noise_std <= 0.0:
        return base
    noisy = video.frames + baseline_noise_std
    # Degenerate baseline: if we send noise as zero predictor, this is deliberately
    # pessimistic but still useful for sanity checks.
    mse = float((noisy - noisy.mean(axis=0)).var() + 1e-12)
    return {
        "raw_bytes": int(video.frames.astype(float).nbytes),
        "noisy_raw_bytes": int(video.frames.astype(float).nbytes),
        "rmse": float(mse ** 0.5),
        "mae": float(abs(noisy - noisy.mean(axis=0)).mean()),
        "max_abs": float(abs(noisy - noisy.mean(axis=0)).max()),
        "r2": 0.0,
    }


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "row_count": 0,
            "best_compression_ratio": 0.0,
            "best_r2": 0.0,
            "beats_raw_bytes_count": 0,
            "best_row": None,
        }
    best_ratio_row = max(rows, key=lambda row: float(row["compression_ratio"]))
    best_r2_row = max(rows, key=lambda row: float(row["r2"]))
    return {
        "row_count": len(rows),
        "best_compression_ratio": float(best_ratio_row["compression_ratio"]),
        "best_r2": float(best_r2_row["r2"]),
        "beats_raw_bytes_count": int(sum(1 for row in rows if row.get("beats_raw_bytes", 0) > 0)),
        "best_row": {
            "frame_count": best_ratio_row["frame_count"],
            "rank": best_ratio_row["rank"],
            "temporal_terms": best_ratio_row["temporal_terms"],
            "compression_ratio": _format_float(best_ratio_row["compression_ratio"]),
            "r2": _format_float(best_ratio_row["r2"]),
        },
        "best_r2_row": {
            "frame_count": best_r2_row["frame_count"],
            "rank": best_r2_row["rank"],
            "temporal_terms": best_r2_row["temporal_terms"],
            "r2": _format_float(best_r2_row["r2"]),
            "compression_ratio": _format_float(best_r2_row["compression_ratio"]),
        },
    }


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
        f"{value.get('frame_count')} / r{value.get('rank')} / t{value.get('temporal_terms')} -> "
        f"ratio={value.get('compression_ratio')} r2={value.get('r2')}"
    )
