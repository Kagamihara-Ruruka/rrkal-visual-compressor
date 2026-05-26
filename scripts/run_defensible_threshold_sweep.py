from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from vizcompress.benchmarks import benchmark_synthetic_sizes
from vizcompress.benchmarks import _format_float


def _parse_thresholds(value: str) -> list[float]:
    thresholds = [float(item.strip()) for item in value.split(",") if item.strip()]
    if not thresholds:
        raise ValueError("at least one threshold is required")
    return thresholds


def run_threshold_sweep(*, sample_sizes: list[int], synthetic_kind: str, fourier_terms: int, rdp_epsilon: float,
                       svg_samples: int, channel: bool, channel_k: float, channel_window: int,
                       channel_band_epsilon: float, thresholds: list[float],
                       smooth_window: int, sigma_clip: float | None,
                       noise_layer_terms: int, auto_noise_layer: bool,
                       x_domain_policy: str, x_domain_epsilon: float, x_domain_max_error: float) -> dict[str, Any]:
    points = []
    for threshold in thresholds:
        data = benchmark_synthetic_sizes(
            sample_sizes,
            synthetic_kind=synthetic_kind,
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
            defensible_channel_coverage_threshold=threshold,
        )

        summary = data["summary"]
        points.append(
            {
                "threshold": threshold,
                "high_fidelity_rows_count": summary.get("high_fidelity_rows_count", 0),
                "defensible_rows_count": summary.get("defensible_rows_count", 0),
                "defensible_rows_ratio": summary.get("defensible_rows_ratio", 0.0),
                "best_ratio": summary.get("best_direct_svg_gzip_to_package_ratio"),
                "best_high_fidelity_ratio": (summary.get("best_high_fidelity_svg_gzip_candidate") or {}).get(
                    "ratio"
                ),
                "best_defensible_ratio": (summary.get("best_defensible_high_fidelity_svg_gzip_candidate") or {}).get(
                    "ratio"
                ),
                "sample": (summary.get("best_rows") or {}).get("direct_svg_gzip", {}).get("samples"),
            }
        )

    return {
        "benchmark": "defensible_threshold_sweep",
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
            "thresholds": thresholds,
        },
        "sweep": points,
    }


def format_threshold_sweep_markdown(result: dict[str, Any], summary: str = "") -> str:
    params = result["parameters"]
    sweep = result["sweep"]

    lines = [
        "# Defensible Threshold Sweep",
        "",
        "## Parameters",
        f"- Synthetic kind: `{params.get('synthetic_kind')}`",
        f"- Sample sizes: `{params.get('sample_sizes')}`",
        f"- Fourier terms: `{params.get('fourier_terms')}`",
        f"- Channel K: `{params.get('channel_k')}`",
        f"- Channel window: `{params.get('channel_window')}`",
        f"- Channel band epsilon: `{params.get('channel_band_epsilon')}`",
        f"- SVG samples: `{params.get('svg_samples')}`",
        "",
    ]
    if summary:
        lines.append(summary)

    lines.extend([
        "",
        "## Sweep",
        "",
        "| threshold | high-fidelity | defensible | defensible ratio | best SVG.gz | best defensible SVG.gz | best high-fidelity SVG.gz |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])

    for item in sweep:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"{item['threshold']}",
                    str(item["high_fidelity_rows_count"]),
                    str(item["defensible_rows_count"]),
                    f"{_format_float(item['defensible_rows_ratio'] * 100)}%",
                    f"{_format_float(item['best_ratio'])}",
                    f"{_format_float(item['best_defensible_ratio']) if item['best_defensible_ratio'] is not None else 'n/a'}",
                    f"{_format_float(item['best_high_fidelity_ratio'])}",
                ]
            )
            + " |"
        )

    lines.extend(["", "## Interpretation", "", summary or "No additional interpretation."])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run defensible-channel coverage threshold sensitivity sweep.")
    parser.add_argument("--sample-sizes", default="10000", help="Comma-separated synthetic sample counts.")
    parser.add_argument("--synthetic-kind", default="smooth")
    parser.add_argument("--fourier-terms", type=int, default=16)
    parser.add_argument("--rdp-epsilon", type=float, default=0.6)
    parser.add_argument("--svg-samples", type=int, default=240)
    parser.add_argument("--channel", action="store_true", default=True)
    parser.add_argument("--channel-k", type=float, default=3.0)
    parser.add_argument("--channel-window", type=int, default=16)
    parser.add_argument("--channel-band-epsilon", type=float, default=0.04)
    parser.add_argument("--thresholds", default="0.8,0.9,0.95,0.98,0.995")
    parser.add_argument("--out-json", default="docs/benchmarks/defensible_threshold_sweep.json")
    parser.add_argument("--out-md", default="docs/benchmarks/defensible_threshold_sweep.md")
    parser.add_argument("--smooth-window", type=int, default=1)
    parser.add_argument("--sigma-clip", type=float, default=None)
    parser.add_argument("--noise-layer-terms", type=int, default=0)
    parser.add_argument("--auto-noise-layer", action="store_true")
    parser.add_argument("--x-domain-policy", default="preserve")
    parser.add_argument("--x-domain-epsilon", type=float, default=0.002)
    parser.add_argument("--x-domain-max-error", type=float, default=1e-4)
    return parser.parse_args()


def _parse_sample_sizes(value: str) -> list[int]:
    sizes = [int(item.strip()) for item in value.split(",") if item.strip()]
    if not sizes:
        raise ValueError("at least one sample size is required")
    if any(size < 2 for size in sizes):
        raise ValueError("sample sizes must be >= 2")
    return sizes


def main() -> int:
    args = parse_args()
    args.sample_sizes = _parse_sample_sizes(args.sample_sizes)
    args.thresholds = _parse_thresholds(args.thresholds)
    result = run_threshold_sweep(
        sample_sizes=args.sample_sizes,
        synthetic_kind=args.synthetic_kind,
        fourier_terms=args.fourier_terms,
        rdp_epsilon=args.rdp_epsilon,
        svg_samples=args.svg_samples,
        channel=args.channel,
        channel_k=args.channel_k,
        channel_window=args.channel_window,
        channel_band_epsilon=args.channel_band_epsilon,
        thresholds=args.thresholds,
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
    summary = (
        "This sweep is intended to show the fragility of coverage-based defensibility. "
        "A high best size ratio is only adopted when the defensible sample count and ratio are also acceptable."
    )
    out_md.write_text(format_threshold_sweep_markdown(result, summary=summary), encoding="utf-8")

    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())