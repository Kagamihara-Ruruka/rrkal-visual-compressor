from __future__ import annotations

import argparse
import json
import sys
import math
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_SRC = ROOT_DIR / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from vizcompress.benchmarks import (
    benchmark_synthetic_terms_channel_k_sweep,
    evaluate_benchmark_gate,
    parse_float_values,
    parse_fourier_terms,
    parse_sample_sizes,
)


def parse_synthetic_kinds(value: str) -> list[str]:
    kinds = [item.strip() for item in value.split(",") if item.strip()]
    if not kinds:
        raise ValueError("at least one synthetic kind is required")
    if "all" in kinds and len(kinds) > 1:
        raise ValueError("'all' cannot be combined with other kinds")
    return kinds


def parse_thresholds(value: str) -> list[float]:
    thresholds = [float(item.strip()) for item in value.split(",") if item.strip()]
    if not thresholds:
        raise ValueError("at least one threshold is required")
    if any(value < 0.0 or value > 1.0 for value in thresholds):
        raise ValueError("threshold values must be in [0,1]")
    return thresholds


def _format_float(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, (int, float)):
        return f"{float(value):.6g}"
    return str(value)


def _format_bool(value: Any) -> str:
    return "yes" if value else "no"


def _ratio_from_value(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _ratio_candidates(ratio_field: str) -> tuple[str, ...]:
    if ratio_field == "direct_svg_gzip_to_package_ratio":
        return ("direct_svg_gzip_to_package_ratio", "direct_svg_to_package_ratio")
    return (ratio_field,)


def _ratio(row: dict[str, Any] | None, ratio_field: str) -> float | None:
    if row is None:
        return None
    for key in _ratio_candidates(ratio_field):
        value = _ratio_from_value(row.get(key))
        if value is not None:
            return value
    return None


def _best_row(rows: list[dict[str, Any]], ratio_field: str) -> dict[str, Any] | None:
    candidates = [(row, value) for row in rows if (value := _ratio(row, ratio_field)) is not None]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[1])[0]


def _meets_channel_coverage(row: dict[str, Any], threshold: float) -> bool:
    channel_coverage = _ratio_from_value(row.get("channel_coverage_ratio"))
    return channel_coverage is None or channel_coverage >= threshold


def _extract_by_kind(summary_by_kind: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        kind: {
            "high_fidelity_rows_count": int(payload.get("high_fidelity_rows_count", 0)),
            "defensible_rows_count": int(payload.get("defensible_rows_count", 0)),
            "defensible_rows_ratio": float(payload.get("defensible_rows_ratio", 0.0)),
            "best_ratio": _ratio_from_value(
                (payload.get("best_rows", {}).get("direct_svg_gzip") or {}).get("ratio")
            ),
            "best_defensible_ratio": _ratio_from_value(
                (payload.get("best_defensible_high_fidelity_svg_gzip_candidate") or {}).get("ratio")
            ),
        }
        for kind, payload in summary_by_kind.items()
    }


def run_kind_threshold_sweep(
    *,
    sample_sizes: list[int],
    synthetic_kinds: list[str],
    fourier_terms_values: list[int],
    channel_k_values: list[float],
    rdp_epsilon: float,
    svg_samples: int,
    channel_window: int,
    channel_band_epsilon: float,
    thresholds: list[float],
    smooth_window: int,
    sigma_clip: float | None,
    noise_layer_terms: int,
    auto_noise_layer: bool,
    x_domain_policy: str,
    x_domain_epsilon: float,
    x_domain_max_error: float,
    require_svg_gzip_win: bool = False,
    require_csv_gzip_win: bool = False,
    min_fourier_r2: float | None = None,
    min_channel_coverage: float | None = None,
    min_defensible_rows_ratio: float | None = None,
    min_high_fidelity_rows: int | None = None,
) -> dict[str, Any]:
    if not synthetic_kinds:
        raise ValueError("synthetic_kinds must not be empty")

    sweep = []
    kind_union = set()
    for threshold in thresholds:
        rows = []
        for kind in synthetic_kinds:
            payload = benchmark_synthetic_terms_channel_k_sweep(
                sample_sizes,
                fourier_terms_values=fourier_terms_values,
                channel_k_values=channel_k_values,
                synthetic_kind=kind,
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
            rows.extend(payload.get("rows", []))
            kind_union.add(kind)

        summary = _summarize_rows(rows, threshold)
        by_kind = _extract_by_kind(summary.get("summary_by_kind", {}))
        by_terms_k = summary.get("summary_by_terms_k", {})
        best_cells = {
            key: _ratio_from_value((value.get("best_rows", {}).get("direct_svg_gzip") or {}).get("ratio"))
            for key, value in by_terms_k.items()
        }

        all_best = summary.get("best_rows", {}).get("direct_svg_gzip", {})
        gate = evaluate_benchmark_gate(
            {"rows": rows, "summary": summary},
            require_svg_gzip_win=require_svg_gzip_win,
            require_csv_gzip_win=require_csv_gzip_win,
            min_fourier_r2=min_fourier_r2,
            min_channel_coverage=min_channel_coverage,
            min_defensible_rows_ratio=min_defensible_rows_ratio,
            min_high_fidelity_rows=min_high_fidelity_rows,
        )

        sweep.append(
            {
                "threshold": threshold,
                "high_fidelity_rows_count": summary.get("high_fidelity_rows_count", 0),
                "defensible_rows_count": summary.get("defensible_rows_count", 0),
                "defensible_rows_ratio": summary.get("defensible_rows_ratio", 0.0),
                "best_ratio": summary.get("best_direct_svg_gzip_to_package_ratio"),
                "best_defensible_ratio": (summary.get("best_defensible_high_fidelity_svg_gzip_candidate") or {}).get(
                    "ratio"
                ),
                "best_global_sample_count": summary.get("best_ratio_samples"),
                "best_global_samples": summary.get("best_direct_svg_gzip_ratio_samples"),
                "rows_by_kind": by_kind,
                "rows_by_terms_k": by_terms_k,
                "term_k_best_rows": best_cells,
                "global_best_row": all_best,
                "benchmark_gate": gate,
            }
        )

    return {
        "benchmark": "terms_channel_kind_threshold_grid_sweep",
        "parameters": {
            "sample_sizes": sample_sizes,
            "synthetic_kinds": sorted(synthetic_kinds),
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
            "kind_union": sorted(kind_union),
            "gate_policy": {
                "require_svg_gzip_win": require_svg_gzip_win,
                "require_csv_gzip_win": require_csv_gzip_win,
                "min_fourier_r2": min_fourier_r2,
                "min_channel_coverage": min_channel_coverage,
                "min_defensible_rows_ratio": min_defensible_rows_ratio,
                "min_high_fidelity_rows": min_high_fidelity_rows,
            },
        },
        "sweep": sweep,
    }


def _summarize_rows(rows: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    from collections import defaultdict as _defaultdict

    def _safekey(row: dict[str, Any]) -> str:
        return f"{row.get('synthetic_kind')}|{row.get('samples')}|{row.get('fourier_terms')}|{row.get('channel_k')}"

    by_kind = _defaultdict(list)
    for row in rows:
        by_kind[row.get("synthetic_kind")].append(row)

    summary = {
        "high_fidelity_rows_count": len([row for row in rows if row.get("fourier_r2", 0.0) >= 0.99]),
        "defensible_rows_count": 0,
        "defensible_rows_ratio": 0.0,
        "package_wins_against_direct_svg_gzip_count": 0,
        "package_wins_against_source_csv_gzip_count": 0,
        "best_rows": {
            "direct_svg_gzip": {},
        },
        "best_direct_svg_gzip_to_package_ratio": 0.0,
        "best_defensible_high_fidelity_svg_gzip_candidate": None,
        "summary_by_kind": {},
        "summary_by_terms_k": {},
        "rows": rows,
    }
    high_fidelity_rows = [row for row in rows if row.get("fourier_r2", 0.0) >= 0.99]
    defensible_rows = [row for row in high_fidelity_rows if _meets_channel_coverage(row, threshold)]
    summary["defensible_rows_count"] = len(defensible_rows)
    summary["defensible_rows_ratio"] = len(defensible_rows) / len(high_fidelity_rows) if high_fidelity_rows else 0.0

    if rows:
        best_global = _best_row(rows, "direct_svg_gzip_to_package_ratio")
        best_global_ratio = _ratio(best_global, "direct_svg_gzip_to_package_ratio")
        if best_global is not None:
            summary["best_rows"]["direct_svg_gzip"] = {
                "synthetic_kind": best_global.get("synthetic_kind"),
                "samples": best_global.get("samples"),
                "fourier_terms": best_global.get("fourier_terms"),
                "channel_k": best_global.get("channel_k"),
                "ratio": best_global_ratio,
            }
            summary["best_direct_svg_gzip_to_package_ratio"] = best_global_ratio
            summary["best_ratio_samples"] = best_global.get("samples")
            summary["best_direct_svg_gzip_ratio_samples"] = best_global.get("samples")
        summary["package_wins_against_direct_svg_gzip_count"] = len(
            [row for row in rows if (_ratio(row, "direct_svg_gzip_to_package_ratio") or 0.0) > 1.0]
        )
        summary["package_wins_against_source_csv_gzip_count"] = len(
            [row for row in rows if (_ratio(row, "source_csv_gzip_to_package_ratio") or 0.0) > 1.0]
        )

    if defensible_rows:
        best_def = _best_row(defensible_rows, "direct_svg_gzip_to_package_ratio")
        best_def_ratio = _ratio(best_def, "direct_svg_gzip_to_package_ratio")
        if best_def is not None:
            summary["best_defensible_high_fidelity_svg_gzip_candidate"] = {
                "synthetic_kind": best_def.get("synthetic_kind"),
                "samples": best_def.get("samples"),
                "fourier_terms": best_def.get("fourier_terms"),
                "channel_k": best_def.get("channel_k"),
                "ratio": best_def_ratio,
            }

    for kind, items in by_kind.items():
        hk = len([row for row in items if row.get("fourier_r2", 0.0) >= 0.99])
        defensible_hk = [
            row for row in items if row.get("fourier_r2", 0.0) >= 0.99 and _meets_channel_coverage(row, threshold)
        ]
        best_kind = _best_row(items, "direct_svg_gzip_to_package_ratio")
        summary["summary_by_kind"][kind] = {
            "high_fidelity_rows_count": hk,
            "defensible_rows_count": len(defensible_hk),
            "defensible_rows_ratio": len(defensible_hk) / hk if hk else 0.0,
            "best_rows": {
                "direct_svg_gzip": {
                    "ratio": _ratio(best_kind, "direct_svg_gzip_to_package_ratio") or 0.0,
                }
            },
        }

    for term in sorted({int(row["fourier_terms"]) for row in rows}):
        for k_value in sorted({float(row["channel_k"]) for row in rows if int(row["fourier_terms"]) == term and row.get("channel_k") is not None}):
            key = f"{term}|{k_value}"
            items = [row for row in rows if int(row["fourier_terms"]) == term and row.get("channel_k") == k_value]
            if not items:
                continue
            best = _best_row(items, "direct_svg_gzip_to_package_ratio")
            best_h = [row for row in items if row.get("fourier_r2", 0.0) >= 0.99 and _meets_channel_coverage(row, threshold)]
            best_ratio = _ratio(best, "direct_svg_gzip_to_package_ratio")
            summary["summary_by_terms_k"][key] = {
                "high_fidelity_rows_count": len([row for row in items if row.get("fourier_r2", 0.0) >= 0.99]),
                "defensible_rows_count": len(best_h),
                "defensible_rows_ratio": len(best_h) / len([row for row in items if row.get("fourier_r2", 0.0) >= 0.99]) if any(
                    row.get("fourier_r2", 0.0) >= 0.99 for row in items
                ) else 0.0,
                "best_rows": {
                    "direct_svg_gzip": {
                        "samples": best.get("samples") if best is not None else None,
                        "ratio": best_ratio or 0.0,
                    }
                },
                "best_defensible_high_fidelity_svg_gzip_candidate": (
                    {
                        "samples": _best["samples"],
                        "ratio": _ratio(_best, "direct_svg_gzip_to_package_ratio"),
                    }
                    if (_best := _best_row(best_h, "direct_svg_gzip_to_package_ratio"))
                    else None
                ),
            }

    return summary


def format_markdown(result: dict[str, Any]) -> str:
    params = result["parameters"]
    lines = [
        "# Terms x Channel-K x Threshold x Kind Sweep",
        "",
        "## Parameters",
        f"- Synthetic kinds: `{params.get('synthetic_kinds')}`",
        f"- Sample sizes: `{params.get('sample_sizes')}`",
        f"- Fourier terms: `{params.get('fourier_terms_values')}`",
        f"- Channel-K values: `{params.get('channel_k_values')}`",
        f"- Thresholds: `{params.get('thresholds')}`",
        f"- RDP epsilon: `{params.get('rdp_epsilon')}`",
        f"- SVG samples: `{params.get('svg_samples')}`",
        "",
        "## Global sweep",
        "| threshold | high-fidelity | defensible | defensible ratio | best gzip ratio | best defensible ratio | gate ok |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for point in result["sweep"]:
        gate_ok = "yes" if bool(point.get("benchmark_gate", {}).get("ok", False)) else "no"
        lines.append(
            "| "
            + " | ".join(
                [
                    str(point["threshold"]),
                    str(point["high_fidelity_rows_count"]),
                    str(point["defensible_rows_count"]),
                    f"{_format_float(point['defensible_rows_ratio'] * 100)}%",
                    _format_float(point["best_ratio"]),
                    _format_float(point["best_defensible_ratio"]),
                    gate_ok,
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Per-kind stability",
            "",
            "| threshold | kind | high-fidelity | defensible | defensible ratio | best ratio | best defensible ratio |",
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )

    for point in result["sweep"]:
        threshold = point["threshold"]
        for kind in sorted(point["rows_by_kind"]):
            payload = point["rows_by_kind"][kind]
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(threshold),
                        kind,
                        str(payload.get("high_fidelity_rows_count", 0)),
                        str(payload.get("defensible_rows_count", 0)),
                        f"{_format_float(payload.get('defensible_rows_ratio', 0.0) * 100)}%",
                        _format_float(payload.get("best_ratio")),
                        _format_float(payload.get("best_defensible_ratio")),
                    ]
                )
                + " |"
            )

    lines.extend(
        [
            "",
            "## Top cells by threshold",
            "",
            "| threshold | term | K | best samples | best ratio |",
            "| ---: | ---: | ---: | ---: | ---: |",
        ]
    )

    for point in result["sweep"]:
        threshold = point["threshold"]
        terms_k = point["rows_by_terms_k"]
        if not terms_k:
            continue
        best_key = max(
            terms_k.items(),
            key=lambda item: (_ratio_from_value(
                (item[1].get("best_rows", {}).get("direct_svg_gzip") or {}).get("ratio")
            ) or 0.0),
        )[0]
        best_entry = terms_k[best_key]
        best_row = (best_entry.get("best_rows", {}).get("direct_svg_gzip")) or {}
        term, k = best_key.split("|", 1)
        lines.append(
            "| "
            + " | ".join(
                [
                    str(threshold),
                    term,
                    k,
                    str(best_row.get("samples", "")),
                    _format_float(best_row.get("ratio")),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Gate outcomes",
            "| threshold | ok | errors |",
            "| ---: | ---: | --- |",
        ]
    )
    for point in result["sweep"]:
        gate = point.get("benchmark_gate", {})
        lines.append(
            "| "
            + " | ".join(
                [
                    str(point["threshold"]),
                    _format_bool(gate.get("ok")),
                    "; ".join(gate.get("errors", [])) or "pass",
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run terms/channel/threshold sweep over synthetic kind set.")
    parser.add_argument("--sample-sizes", default="10000", help="Comma-separated sample counts.")
    parser.add_argument("--synthetic-kinds", default="all", help="Comma-separated kinds or all.")
    parser.add_argument("--fourier-terms", default="16,32,64", help="Comma-separated term counts.")
    parser.add_argument("--channel-k", default="2,3,4", help="Comma-separated channel K values.")
    parser.add_argument("--channel-window", type=int, default=16)
    parser.add_argument("--channel-band-epsilon", type=float, default=0.04)
    parser.add_argument("--rdp-epsilon", type=float, default=0.6)
    parser.add_argument("--svg-samples", type=int, default=240)
    parser.add_argument("--thresholds", default="0.90,0.92,0.95,0.98")
    parser.add_argument("--smooth-window", type=int, default=1)
    parser.add_argument("--sigma-clip", type=float, default=None)
    parser.add_argument("--noise-layer-terms", type=int, default=0)
    parser.add_argument("--auto-noise-layer", action="store_true")
    parser.add_argument("--out-json", default="docs/benchmarks/terms_channel_kind_threshold_grid.json")
    parser.add_argument("--out-md", default="docs/benchmarks/terms_channel_kind_threshold_grid.md")
    parser.add_argument("--x-domain-policy", default="preserve")
    parser.add_argument("--x-domain-epsilon", type=float, default=0.002)
    parser.add_argument("--x-domain-max-error", type=float, default=1e-4)
    parser.add_argument("--require-svg-gzip-win", action="store_true")
    parser.add_argument("--require-csv-gzip-win", action="store_true")
    parser.add_argument("--min-fourier-r2", type=float, default=None)
    parser.add_argument("--min-channel-coverage", type=float, default=None)
    parser.add_argument("--min-defensible-ratio", type=float, default=None)
    parser.add_argument("--min-high-fidelity-rows", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sample_sizes = parse_sample_sizes(args.sample_sizes)
    synthetic_kinds = parse_synthetic_kinds(args.synthetic_kinds)
    fourier_terms_values = parse_fourier_terms(args.fourier_terms)
    channel_k_values = parse_float_values(args.channel_k, name="channel K", minimum=0.0)
    thresholds = parse_thresholds(args.thresholds)

    if synthetic_kinds == ["all"]:
        from vizcompress.data import SYNTHETIC_KINDS

        synthetic_kinds = list(SYNTHETIC_KINDS)

    result = run_kind_threshold_sweep(
        sample_sizes=sample_sizes,
        synthetic_kinds=synthetic_kinds,
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
        require_svg_gzip_win=args.require_svg_gzip_win,
        require_csv_gzip_win=args.require_csv_gzip_win,
        min_fourier_r2=args.min_fourier_r2,
        min_channel_coverage=args.min_channel_coverage,
        min_defensible_rows_ratio=args.min_defensible_ratio,
        min_high_fidelity_rows=args.min_high_fidelity_rows,
    )

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    out_md.write_text(format_markdown(result), encoding="utf-8")
    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
