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

from vizcompress.benchmarks import (
    benchmark_synthetic_terms_channel_k_sweep,
)
from vizcompress.benchmarks import parse_float_values, parse_fourier_terms


def parse_sample_sizes(value: str) -> list[int]:
    sizes = [int(item.strip()) for item in value.split(",") if item.strip()]
    if not sizes:
        raise ValueError("at least one sample size is required")
    if any(size < 2 for size in sizes):
        raise ValueError("sample sizes must be >= 2")
    return sizes


def format_float(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return f"{float(value):.6g}"
    return str(value)


def _extract_best_row(
    summary_by_terms_k: dict[str, Any],
    ratio_key: str,
) -> tuple[str, dict[str, Any]]:
    candidates = [
        (key, payload.get("best_rows", {}).get("direct_svg_gzip", {}))
        for key, payload in summary_by_terms_k.items()
    ]
    candidates = [(key, candidate) for key, candidate in candidates if isinstance(candidate, dict) and candidate.get(ratio_key)]
    if not candidates:
        return "", {}
    key, best = max(candidates, key=lambda item: float(item[1][ratio_key]))
    return key, best


def format_grid_markdown(result: dict[str, Any]) -> str:
    params = result["parameters"]
    summary = result["summary"]
    by_grid = result.get("summary_by_terms_k", {})
    best_key, best_grid = _extract_best_row(by_grid, "ratio")

    lines = [
        "# Fourier Terms x Channel-K Sweep",
        "",
        "## Parameters",
        f"- Sample sizes: `{params.get('sample_sizes')}`",
        f"- Fourier terms: `{params.get('fourier_terms_values')}`",
        f"- Channel K values: `{params.get('channel_k_values')}`",
        f"- RDP epsilon: `{params.get('rdp_epsilon')}`",
        f"- SVG samples: `{params.get('svg_samples')}`",
        f"- Defensible threshold: `{summary.get('defensible_channel_coverage_threshold')}`",
        "",
        "## High-level",
        f"- Overall best SVG.gz ratio: `{format_float(summary.get('best_direct_svg_gzip_to_package_ratio'))}`",
        f"- High-fidelity rows: `{summary.get('high_fidelity_rows_count', 0)}`",
        f"- Defensible rows: `{summary.get('defensible_rows_count', 0)} ({format_float(summary.get('defensible_rows_ratio', 0) * 100)}%)`",
        f"- Best defensible row: `{best_key}`",
        "",
        "## Grid summary",
        "",
        "| term | K | samples | gzip ratio | high-fidelity | defensible | coverage | channel rows |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for key in sorted(by_grid):
        term_str, k_str = key.split("|", 1)
        payload = by_grid[key]
        best = payload.get("best_rows", {}).get("direct_svg_gzip", {})
        if not isinstance(best, dict):
            best = {}
        lines.append(
            "| "
            + " | ".join(
                [
                    term_str,
                    k_str,
                    str(best.get("samples", "")),
                    format_float(best.get("ratio", 0.0)),
                    str(payload.get("high_fidelity_rows_count", "")),
                    str(payload.get("defensible_rows_count", "")),
                    format_float(payload.get("defensible_rows_ratio", 0.0)),
                    str(best.get("package_bytes", "")),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Execution policy",
            "- If `defensible_rows_count=0`, high compressibility did not remain stable under the defended threshold.",
            "- Compare `best_rows.direct_svg_gzip.ratio` and `best_defensible...` in raw JSON for precise policy choice.",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Fourier terms x channel-K sweep.")
    parser.add_argument("--sample-sizes", default="10000", help="Comma-separated sample counts.")
    parser.add_argument("--synthetic-kind", default="smooth")
    parser.add_argument("--fourier-terms", default="16,32,64", help="Comma-separated term counts.")
    parser.add_argument("--channel-k", default="2,3,4", help="Comma-separated channel K values.")
    parser.add_argument("--channel-window", type=int, default=16)
    parser.add_argument("--channel-band-epsilon", type=float, default=0.04)
    parser.add_argument("--rdp-epsilon", type=float, default=0.6)
    parser.add_argument("--svg-samples", type=int, default=240)
    parser.add_argument("--smooth-window", type=int, default=1)
    parser.add_argument("--sigma-clip", type=float, default=None)
    parser.add_argument("--noise-layer-terms", type=int, default=0)
    parser.add_argument("--auto-noise-layer", action="store_true")
    parser.add_argument("--out-json", default="docs/benchmarks/terms_channel_k_grid.json")
    parser.add_argument("--out-md", default="docs/benchmarks/terms_channel_k_grid.md")
    parser.add_argument("--x-domain-policy", default="preserve")
    parser.add_argument("--x-domain-epsilon", type=float, default=0.002)
    parser.add_argument("--x-domain-max-error", type=float, default=1e-4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sample_sizes = parse_sample_sizes(args.sample_sizes)
    fourier_terms_values = parse_fourier_terms(args.fourier_terms)
    channel_k_values = parse_float_values(args.channel_k, name="channel K", minimum=0.0)
    result = benchmark_synthetic_terms_channel_k_sweep(
        sample_sizes,
        fourier_terms_values=fourier_terms_values,
        channel_k_values=channel_k_values,
        synthetic_kind=args.synthetic_kind,
        rdp_epsilon=args.rdp_epsilon,
        svg_samples=args.svg_samples,
        channel_window=args.channel_window,
        channel_band_epsilon=args.channel_band_epsilon,
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
    out_md.write_text(format_grid_markdown(result), encoding="utf-8")
    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

