from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_SRC = ROOT_DIR / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from vizcompress.benchmarks import benchmark_synthetic_terms_channel_k_sweep
from vizcompress.benchmarks import parse_float_values, parse_fourier_terms


def parse_sample_sizes(value: str) -> list[int]:
    sizes = [int(item.strip()) for item in value.split(",") if item.strip()]
    if not sizes:
        raise ValueError("at least one sample size is required")
    if any(size < 2 for size in sizes):
        raise ValueError("sample sizes must be >= 2")
    return sizes


def parse_thresholds(value: str) -> list[float]:
    thresholds = [float(item.strip()) for item in value.split(",") if item.strip()]
    if not thresholds:
        raise ValueError("at least one threshold is required")
    return thresholds


def _format_float(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, (int, float)):
        return f"{float(value):.6g}"
    return str(value)


def _format_bool(value: Any) -> str:
    return "yes" if value else "no"


def _extract_grid_cells(summary_by_terms_k: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        key: {
            "high_fidelity_rows_count": int(value.get("high_fidelity_rows_count", 0)),
            "defensible_rows_count": int(value.get("defensible_rows_count", 0)),
            "defensible_rows_ratio": float(value.get("defensible_rows_ratio", 0.0)),
            "best_defensible_ratio": (value.get("best_defensible_high_fidelity_svg_gzip_candidate") or {}).get("ratio"),
            "best_ratio": (value.get("best_rows", {}).get("direct_svg_gzip") or {}).get("ratio"),
        }
        for key, value in summary_by_terms_k.items()
    }


def run_threshold_grid(*, sample_sizes: list[int], synthetic_kind: str, fourier_terms_values: list[int],
                       channel_k_values: list[float], rdp_epsilon: float, svg_samples: int,
                       channel_window: int, channel_band_epsilon: float, thresholds: list[float],
                       smooth_window: int, sigma_clip: float | None, noise_layer_terms: int,
                       auto_noise_layer: bool, x_domain_policy: str, x_domain_epsilon: float,
                       x_domain_max_error: float) -> dict[str, Any]:
    points = []
    terms_k_cells: set[str] = set()
    for threshold in thresholds:
        data = benchmark_synthetic_terms_channel_k_sweep(
            sample_sizes,
            fourier_terms_values=fourier_terms_values,
            channel_k_values=channel_k_values,
            synthetic_kind=synthetic_kind,
            rdp_epsilon=rdp_epsilon,
            svg_samples=svg_samples,
            channel_window=channel_window,
            channel_band_epsilon=channel_band_epsilon,
            smooth_window=smooth_window,
            sigma_clip=sigma_clip,
            noise_layer_terms=noise_layer_terms,
            auto_noise_layer=auto_noise_layer,
            x_domain_policy=x_domain_policy,
            x_domain_epsilon=x_domain_epsilon,
            x_domain_max_error=x_domain_max_error,
            defensible_channel_coverage_threshold=threshold,
        )
        summary = data["summary"]
        cell_summary = _extract_grid_cells(data.get("summary_by_terms_k", {}))
        terms_k_cells.update(cell_summary.keys())

        points.append(
            {
                "threshold": threshold,
                "high_fidelity_rows_count": summary.get("high_fidelity_rows_count", 0),
                "defensible_rows_count": summary.get("defensible_rows_count", 0),
                "defensible_rows_ratio": summary.get("defensible_rows_ratio", 0.0),
                "best_ratio": summary.get("best_direct_svg_gzip_to_package_ratio"),
                "best_defensible_ratio": (summary.get("best_defensible_high_fidelity_svg_gzip_candidate") or {}).get(
                    "ratio"
                ),
                "cells": cell_summary,
            }
        )

    return {
        "benchmark": "terms_channel_threshold_grid_sweep",
        "parameters": {
            "sample_sizes": sample_sizes,
            "synthetic_kind": synthetic_kind,
            "fourier_terms_values": fourier_terms_values,
            "channel_k_values": channel_k_values,
            "rdp_epsilon": rdp_epsilon,
            "svg_samples": svg_samples,
            "channel_window": channel_window,
            "channel_band_epsilon": channel_band_epsilon,
            "smooth_window": smooth_window,
            "sigma_clip": sigma_clip,
            "noise_layer_terms": noise_layer_terms,
            "auto_noise_layer": auto_noise_layer,
            "x_domain_policy": x_domain_policy,
            "x_domain_epsilon": x_domain_epsilon,
            "x_domain_max_error": x_domain_max_error,
            "thresholds": thresholds,
            "cell_keys": sorted(terms_k_cells),
        },
        "sweep": points,
    }


def format_threshold_grid_markdown(result: dict[str, Any]) -> str:
    params = result["parameters"]
    lines = [
        "# Fourier Terms x Channel-K vs Defensible Threshold Sweep",
        "",
        "## Parameters",
        f"- Sample sizes: `{params.get('sample_sizes')}`",
        f"- Fourier terms: `{params.get('fourier_terms_values')}`",
        f"- Channel-K values: `{params.get('channel_k_values')}`",
        f"- Thresholds: `{params.get('thresholds')}`",
        f"- RDP epsilon: `{params.get('rdp_epsilon')}`",
        f"- SVG samples: `{params.get('svg_samples')}`",
        "",
        "## Sweep (global summary)",
        "| threshold | high-fidelity | defensible | defensible ratio | best SVG.gz | best defensible SVG.gz |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for point in result["sweep"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"{point['threshold']}",
                    str(point["high_fidelity_rows_count"]),
                    str(point["defensible_rows_count"]),
                    f"{_format_float(point['defensible_rows_ratio'] * 100)}%",
                    _format_float(point["best_ratio"]),
                    _format_float(point["best_defensible_ratio"]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Cell summary",
            "",
            "| term | K | threshold | high-fidelity | defensible | defensible ratio | best ratio | best defensible ratio | defensible exists |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )

    for point in result["sweep"]:
        threshold = point["threshold"]
        for key in params.get("cell_keys", []):
            cell = point["cells"].get(key, {})
            term, k = key.split("|", 1)
            lines.append(
                "| "
                + " | ".join(
                    [
                        term,
                        k,
                        f"{threshold}",
                        str(cell.get("high_fidelity_rows_count", 0)),
                        str(cell.get("defensible_rows_count", 0)),
                        _format_float(cell.get("defensible_rows_ratio", 0.0) * 100) + "%",
                        _format_float(cell.get("best_ratio")),
                        _format_float(cell.get("best_defensible_ratio")),
                        _format_bool(cell.get("defensible_rows_count", 0) > 0),
                    ]
                )
                + " |"
            )

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Fourier terms x channel-K frontiers across defensible coverage thresholds.",
    )
    parser.add_argument("--sample-sizes", default="10000", help="Comma-separated sample counts.")
    parser.add_argument("--synthetic-kind", default="smooth")
    parser.add_argument("--fourier-terms", default="16,32,64")
    parser.add_argument("--channel-k", default="2,3,4")
    parser.add_argument("--channel-window", type=int, default=16)
    parser.add_argument("--channel-band-epsilon", type=float, default=0.04)
    parser.add_argument("--rdp-epsilon", type=float, default=0.6)
    parser.add_argument("--svg-samples", type=int, default=240)
    parser.add_argument("--thresholds", default="0.90,0.92,0.95,0.98,0.995")
    parser.add_argument("--smooth-window", type=int, default=1)
    parser.add_argument("--sigma-clip", type=float, default=None)
    parser.add_argument("--noise-layer-terms", type=int, default=0)
    parser.add_argument("--auto-noise-layer", action="store_true")
    parser.add_argument("--out-json", default="docs/benchmarks/terms_channel_k_threshold_grid.json")
    parser.add_argument("--out-md", default="docs/benchmarks/terms_channel_k_threshold_grid.md")
    parser.add_argument("--x-domain-policy", default="preserve")
    parser.add_argument("--x-domain-epsilon", type=float, default=0.002)
    parser.add_argument("--x-domain-max-error", type=float, default=1e-4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sample_sizes = parse_sample_sizes(args.sample_sizes)
    fourier_terms_values = parse_fourier_terms(args.fourier_terms)
    channel_k_values = parse_float_values(args.channel_k, name="channel K", minimum=0.0)
    thresholds = parse_thresholds(args.thresholds)
    result = run_threshold_grid(
        sample_sizes=sample_sizes,
        synthetic_kind=args.synthetic_kind,
        fourier_terms_values=fourier_terms_values,
        channel_k_values=channel_k_values,
        rdp_epsilon=args.rdp_epsilon,
        svg_samples=args.svg_samples,
        channel_window=args.channel_window,
        channel_band_epsilon=args.channel_band_epsilon,
        thresholds=thresholds,
        smooth_window=args.smooth_window,
        sigma_clip=args.sigma_clip,
        noise_layer_terms=args.noise_layer_terms,
        auto_noise_layer=args.auto_noise_layer,
        x_domain_policy=args.x_domain_policy,
        x_domain_epsilon=args.x_domain_epsilon,
        x_domain_max_error=args.x_domain_max_error,
    )

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    out_md.write_text(format_threshold_grid_markdown(result), encoding="utf-8")
    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
