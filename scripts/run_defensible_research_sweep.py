from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_SRC = ROOT_DIR / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from vizcompress.data import make_synthetic_dataset
from vizcompress.metrics import regression_metrics
from vizcompress.research import (
    compress_fourier_piecewise,
    compress_fourier_with_uniform_param,
    compress_haar_threshold,
    compress_piecewise_polynomial,
    compress_multichannel_fourier_pca,
    locality_leakage_metric,
)
from vizcompress.compressors import compress_fourier
from vizcompress.core import TimeSeries


def _benchmark_row(name: str, series: TimeSeries, terms: int, max_breaks: int = 4) -> dict[str, Any]:
    global_model = compress_fourier(series, terms=terms)
    piecewise = compress_fourier_piecewise(series, terms=terms, max_breaks=max_breaks)
    polynomial = compress_piecewise_polynomial(series, degree=3, max_breaks=max_breaks)
    uniform = compress_fourier_with_uniform_param(series, terms=terms, reparametrize_to_uniform=True)
    haar_level = max(1, int(np.floor(np.log2(series.sample_count))) - 1)
    haar = compress_haar_threshold(series, level=min(3, haar_level))

    g_metrics = regression_metrics(series.y, global_model.reconstructed_y)
    p_metrics = regression_metrics(series.y, piecewise.reconstructed_y)
    poly_metrics = regression_metrics(series.y, polynomial.reconstructed_y)
    u_metrics = regression_metrics(series.y, uniform.reconstructed_y)
    h_metrics = regression_metrics(series.y, haar.reconstructed_y)

    return {
        "dataset": name,
        "samples": int(series.sample_count),
        "terms": int(terms),
        "global": {
            "r2": float(g_metrics["r2"]),
            "rmse": float(g_metrics["rmse"]),
            "leakage_ratio": locality_leakage_metric(series, global_model.reconstructed_y, window=64)["leakage_ratio"],
            "max_abs": float(g_metrics["max_abs"]),
        },
        "piecewise_fourier": {
            "r2": float(p_metrics["r2"]),
            "rmse": float(p_metrics["rmse"]),
            "leakage_ratio": locality_leakage_metric(series, piecewise.reconstructed_y, window=64)["leakage_ratio"],
            "segment_count": int(piecewise.metrics["segment_count"]),
        },
        "piecewise_polynomial": {
            "r2": float(poly_metrics["r2"]),
            "rmse": float(poly_metrics["rmse"]),
            "leakage_ratio": locality_leakage_metric(series, polynomial.reconstructed_y, window=64)["leakage_ratio"],
            "segment_count": int(polynomial.metrics["segment_count"]),
            "approx_parameter_count": int(polynomial.metrics["approx_parameter_count"]),
        },
        "uniform_param_fourier": {
            "r2": float(u_metrics["r2"]),
            "rmse": float(u_metrics["rmse"]),
            "max_abs": float(u_metrics["max_abs"]),
        },
        "haar_threshold": {
            "r2": float(h_metrics["r2"]),
            "rmse": float(h_metrics["rmse"]),
            "max_abs": float(h_metrics["max_abs"]),
            "residual_payload_ratio": float(haar.metrics["residual_payload_ratio"]),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run defensible locality and x-domain research benchmark.")
    parser.add_argument("--terms", default="16,32,64")
    parser.add_argument("--out-json", default="docs/benchmarks/defensible_hardening_report.json")
    parser.add_argument("--out-md", default="docs/benchmarks/defensible_hardening_report.md")
    return parser.parse_args()


def _format_float(v: Any) -> str:
    if isinstance(v, (int, float)):
        return f"{float(v):.6g}"
    return str(v)


def main() -> int:
    args = parse_args()
    terms = [int(item.strip()) for item in args.terms.split(",") if item.strip()]
    datasets = [
        ("steps", make_synthetic_dataset(4000, kind="steps")),
        ("spikes", make_synthetic_dataset(4000, kind="spikes")),
        ("irregular", make_synthetic_dataset(4000, kind="irregular")),
        ("multiscale", make_synthetic_dataset(4000, kind="multiscale")),
    ]
    rows = [_benchmark_row(name, series, term) for name, series in datasets for term in terms]

    x = np.linspace(0.0, 1.0, 1500, dtype=np.float64)
    channels = np.column_stack(
        [
            np.sin(2 * np.pi * 7.0 * x),
            0.85 * np.sin(2 * np.pi * 7.0 * x + 0.2),
            0.15 * np.sin(2 * np.pi * 29.0 * x),
        ]
    )
    mc = compress_multichannel_fourier_pca(channels, terms=32, rank=2)
    rows.append(
        {
            "dataset": "channels_multiaxis",
            "samples": int(channels.shape[0]),
            "multichannel_rank": int(mc["rank"]),
            "multichannel_metrics": {
                "rmse": float(mc["metrics"]["rmse"]),
                "mae": float(mc["metrics"]["mae"]),
                "max_abs": float(mc["metrics"]["max_abs"]),
                "parameter_count": float(mc["metrics"]["parameter_count"]),
            },
        }
    )

    payload = {
        "terms": terms,
        "rows": rows,
        "summary": {
            "best_global_r2": max(row["global"]["r2"] for row in rows if "global" in row),
            "best_piecewise_leakage": min(
                row["piecewise_fourier"]["leakage_ratio"] for row in rows if "piecewise_fourier" in row
            ),
            "best_poly_leakage": min(
                row["piecewise_polynomial"]["leakage_ratio"] for row in rows if "piecewise_polynomial" in row
            ),
            "multichannel_rmse": mc["metrics"]["rmse"],
        },
    }

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Defensible Compression Research Report",
        "",
        f"- Terms: `{terms}`",
        f"- Rows: `{len(rows)}`",
        "",
        "| dataset | terms | global R2 | piecewise R2 | poly R2 | global leak | piecewise leak | poly leak |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        if "global" not in row:
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["dataset"]),
                    _format_float(row["terms"]),
                    _format_float(row["global"]["r2"]),
                    _format_float(row["piecewise_fourier"]["r2"]),
                    _format_float(row["piecewise_polynomial"]["r2"]),
                    _format_float(row["global"]["leakage_ratio"]),
                    _format_float(row["piecewise_fourier"]["leakage_ratio"]),
                    _format_float(row["piecewise_polynomial"]["leakage_ratio"]),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Multichannel summary", "", f"- rank = {mc['rank']}", f"- rmse = {mc['metrics']['rmse']:.6g}"])
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
