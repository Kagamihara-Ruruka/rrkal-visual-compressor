from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
import json
import os
import shutil
import stat
import time
from pathlib import Path

from vizcompress.analyzers import analyze_time_series
from vizcompress.benchmarks import (
    benchmark_synthetic_channel_k,
    benchmark_synthetic_fourier_terms,
    benchmark_synthetic_terms_channel_k_sweep,
    benchmark_synthetic_sizes,
    evaluate_benchmark_gate,
    parse_float_values,
    parse_fourier_terms,
    parse_sample_sizes,
    write_benchmark,
    write_benchmark_markdown,
)
from vizcompress.cleaning import residual_time_series, sigma_clip_time_series, smooth_time_series
from vizcompress.compressors import compress_fourier, compress_fourier_channel, compress_rdp
from vizcompress.core import CompressionReport
from vizcompress.data import SYNTHETIC_KINDS, make_synthetic_dataset, read_csv_timeseries
from vizcompress.exporters import write_channel_svg, write_demo, write_direct_svg, write_fourier_svg, write_metrics, write_rdp_svg
from vizcompress.packages import (
    load_vizasset_manifest,
    reconstruct_channel,
    reconstruct_fourier,
    reconstruct_noise_layer,
    reconstruct_retained_signal,
    reconstruct_sparse_residual,
    _validate_manifest_shape,
    validate_vizasset,
    validate_vizasset_source,
    write_vizasset,
)
from vizcompress.residuals import analyze_residual, compress_sparse_residual
from vizcompress.reviews import baseline_size_summary, write_review_packet
from vizcompress.video_benchmarks import (
    benchmark_video_sweep,
    parse_int_list,
    write_video_benchmark,
    write_video_benchmark_markdown,
)
from vizcompress.bench_precheck import precheck_benchmarks


@dataclass(frozen=True)
class BuildConfig:
    synthetic: int | None
    csv: Path | None
    synthetic_kind: str = "smooth"
    x_column: str = "time"
    y_column: str = "value"
    out: Path = Path("vizcompress_outputs")
    rdp_epsilon: float = 0.012
    fourier_terms: int = 96
    svg_samples: int = 2400
    smooth_window: int = 1
    sigma_clip: float | None = None
    noise_layer_terms: int = 0
    auto_noise_layer: bool = False
    direct_svg: bool = False
    channel: bool = False
    channel_band: str = "rolling_std"
    channel_window: int = 501
    channel_k: float = 3.0
    channel_band_epsilon: float = 0.01
    package: bool = False
    package_profile: str = "retain-residual"
    package_name: str | None = None
    x_domain_policy: str = "preserve"
    x_domain_epsilon: float = 0.002
    x_domain_max_error: float = 1e-4
    review_packet: bool = False
    review_source: str = "model-input"
    review_max_rmse: float | None = None
    review_max_mae: float | None = None
    review_max_error: float | None = None
    require_review_pass: bool = False
    clean_output: bool = False


@dataclass(frozen=True)
class InspectConfig:
    package: Path
    samples: int = 1200


@dataclass(frozen=True)
class VerifyConfig:
    package: Path
    samples: int = 1024
    synthetic: int | None = None
    csv: Path | None = None
    synthetic_kind: str = "smooth"
    x_column: str = "time"
    y_column: str = "value"
    signal: str = "retained"
    max_rmse: float | None = None
    max_mae: float | None = None
    max_error: float | None = None
    max_x_error: float | None = 1e-9


@dataclass(frozen=True)
class PackageConfig:
    package: Path
    samples: int = 1200
    include_channel: bool = True
    include_sparse_residual: bool = True
    include_noise_layer: bool = True
    include_retained: bool = True


@dataclass(frozen=True)
class ReconstructConfig(PackageConfig):
    signal: str = "center"


def _series_summary(series: object) -> dict[str, float | int]:
    return {
        "samples": int(series.sample_count),  # type: ignore[attr-defined]
        "x_min": float(series.x.min()),  # type: ignore[attr-defined]
        "x_max": float(series.x.max()),  # type: ignore[attr-defined]
        "y_min": float(series.y.min()),  # type: ignore[attr-defined]
        "y_max": float(series.y.max()),  # type: ignore[attr-defined]
    }


def run_build(config: BuildConfig) -> dict[str, object]:
    if config.synthetic is not None:
        series = make_synthetic_dataset(config.synthetic, kind=config.synthetic_kind)
    elif config.csv is not None:
        series = read_csv_timeseries(config.csv, config.x_column, config.y_column)
    else:
        raise ValueError("build requires --synthetic or --csv input")

    raw_series = series
    cleaning_steps = []
    if config.sigma_clip is not None:
        cleaning = sigma_clip_time_series(series, config.sigma_clip)
        cleaning_steps.append(cleaning.metadata())
        series = cleaning.cleaned
    if config.smooth_window > 1:
        cleaning = smooth_time_series(series, config.smooth_window)
        cleaning_steps.append(cleaning.metadata())
        series = cleaning.cleaned

    out_dir: Path = config.out
    out_dir = _prepare_output_directory(out_dir, clean=config.clean_output, label="build")
    out_dir.mkdir(parents=True, exist_ok=True)

    rdp = compress_rdp(series, config.rdp_epsilon)
    fourier = compress_fourier(series, config.fourier_terms)
    noise = None
    sparse_residual = None
    residual_profile = None
    if config.noise_layer_terms > 0:
        if not cleaning_steps:
            raise ValueError("--noise-layer-terms requires --sigma-clip or --smooth-window")
        residual = residual_time_series(raw_series, series)
        residual_profile = analyze_residual(raw_series, residual).as_dict()
        noise = compress_fourier(residual, config.noise_layer_terms)
    elif config.auto_noise_layer and cleaning_steps:
        residual = residual_time_series(raw_series, series)
        residual_profile = analyze_residual(raw_series, residual).as_dict()
        if residual_profile["recommended_strategy"] == "fourier_residual_layer":
            noise = compress_fourier(residual, max(16, config.fourier_terms // 2))
        elif residual_profile["recommended_strategy"] == "sparse_outlier_layer":
            sparse_residual = compress_sparse_residual(residual)
    profile = analyze_time_series(series).as_dict()
    if cleaning_steps:
        profile["cleaning"] = cleaning_steps
    channel = None
    if config.channel:
        channel = compress_fourier_channel(
            series,
            config.fourier_terms,
            band_method=config.channel_band,
            window=config.channel_window,
            k=config.channel_k,
            band_epsilon=config.channel_band_epsilon,
        )
    report = CompressionReport(
        input_samples=series.sample_count,
        rdp=rdp,
        fourier=fourier,
        channel=channel,
        input_profile=profile,
        noise=noise,
        sparse_residual=sparse_residual,
        residual_profile=residual_profile,
    )

    rdp_svg = write_rdp_svg(out_dir / "rdp_vectorized.svg", series, rdp)
    fourier_svg = write_fourier_svg(
        out_dir / "fourier_vectorized.svg",
        series,
        fourier,
        config.svg_samples,
    )
    outputs = []
    baseline_files = {}
    if config.direct_svg:
        direct_svg = write_direct_svg(out_dir / "direct.svg", series)
        outputs.append(direct_svg.name)
        baseline_files["direct_svg"] = direct_svg
    outputs.extend([rdp_svg.name, fourier_svg.name])
    if channel is not None:
        channel_svg = write_channel_svg(
            out_dir / "fourier_channel.svg",
            series,
            channel,
            config.svg_samples,
        )
        outputs.append(channel_svg.name)
    demo = write_demo(out_dir / "demo.py", series.sample_count, config.fourier_terms)
    outputs.append(demo.name)
    metrics = write_metrics(
        out_dir / "metrics.json",
        report,
        [*outputs, "metrics.json"],
    )
    if config.package:
        package_report = report
        if config.package_profile == "clean":
            package_report = CompressionReport(
                input_samples=report.input_samples,
                rdp=report.rdp,
                fourier=report.fourier,
                channel=report.channel,
                input_profile=report.input_profile,
                residual_profile=report.residual_profile,
            )
        preview = out_dir / ("fourier_channel.svg" if channel is not None else "fourier_vectorized.svg")
        package_name = config.package_name or _default_package_name(config.package_profile)
        package = write_vizasset(
            out_dir / package_name,
            series=series,
            report=package_report,
            preview_svg=preview,
            metrics_json=metrics,
            demo_py=demo,
            package_profile=config.package_profile,
            x_domain_policy=config.x_domain_policy,
            x_domain_epsilon=config.x_domain_epsilon,
            x_domain_max_error=config.x_domain_max_error,
        )
        outputs.append(str(package))
        if config.review_packet:
            review_source = raw_series if config.review_source == "raw-input" else series
            review = write_review_packet(
                package / "review.json",
                package,
                review_source,
                baseline_files=baseline_files,
                max_rmse=config.review_max_rmse,
                max_mae=config.review_max_mae,
                max_error=config.review_max_error,
            )
            outputs.append(str(Path(package.name) / review.name))
            manifest = load_vizasset_manifest(package)
            manifest_files = manifest.setdefault("files", {})
            manifest_files["review"] = {
                "path": review.name,
                "sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
                "bytes": review.stat().st_size,
            }
            (package / "asset.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )
            if config.require_review_pass:
                review_data = json.loads(review.read_text(encoding="utf-8"))
                if not bool(review_data.get("accepted")):
                    raise ValueError(f"review packet did not pass verification: {review}")

    summary = report.as_dict()
    rendered_outputs = [
        str(name) if _is_package_output(str(name)) else str(out_dir / name)
        for name in outputs
    ]
    summary["outputs"] = rendered_outputs + [str(metrics)]
    return summary


def run_inspect(config: InspectConfig) -> dict[str, object]:
    data = run_reconstruct(
        ReconstructConfig(
            package=config.package,
            samples=config.samples,
            signal="retained",
        )
    )
    return {
        "package": data["package"],
        "asset_type": data["manifest"]["asset_type"],
        "schema_version": data["manifest"]["schema_version"],
        "package_profile": data["manifest"].get("package_profile", "unknown"),
        "source": data["manifest"]["source"],
        "primary_method": data["manifest"]["model"]["primary_method"],
        "contains_noise_layer": "noise_layer" in data["manifest"].get("metrics", {}),
        "contains_sparse_residual_layer": "sparse_residual_layer" in data["manifest"].get("metrics", {}),
        "reconstructed": data["reconstructed"],
        "retained": data["retained"],
        "channel": data["channel"],
        "sparse_residual": data["sparse_residual"],
        "noise_layer": data["noise_layer"],
        "files": data["manifest"]["files"],
    }


def run_verify(config: VerifyConfig) -> dict[str, object]:
    if config.synthetic is not None:
        source = make_synthetic_dataset(config.synthetic, kind=config.synthetic_kind)
        result = validate_vizasset_source(
            config.package,
            source,
            signal=config.signal,
            max_rmse=config.max_rmse,
            max_mae=config.max_mae,
            max_error=config.max_error,
            max_x_error=config.max_x_error,
        )
    elif config.csv is not None:
        source = read_csv_timeseries(config.csv, config.x_column, config.y_column)
        result = validate_vizasset_source(
            config.package,
            source,
            signal=config.signal,
            max_rmse=config.max_rmse,
            max_mae=config.max_mae,
            max_error=config.max_error,
            max_x_error=config.max_x_error,
        )
    else:
        result = validate_vizasset(config.package, reconstruction_samples=config.samples)
    return result.as_dict()


def run_reconstruct(config: ReconstructConfig) -> dict[str, object]:
    manifest = load_vizasset_manifest(config.package)
    manifest_errors: list[str] = []
    manifest_warnings: list[str] = []
    _validate_manifest_shape(manifest, manifest_errors, manifest_warnings)
    if manifest_errors:
        raise ValueError(
            f"{config.package}: manifest validation failed: " + "; ".join(manifest_errors)
        )

    if config.signal == "center":
        reconstructed = reconstruct_fourier(config.package, samples=config.samples)
    elif config.signal == "retained":
        reconstructed = reconstruct_retained_signal(config.package, samples=config.samples)
    else:
        raise ValueError(f"unsupported reconstruct signal: {config.signal!r}")
    has_channel = manifest["model"]["primary_method"] == "fourier_channel"
    channel_summary = None
    if config.include_channel and has_channel:
        channel = reconstruct_channel(config.package, samples=config.samples)
        channel_summary = {
            "samples": int(channel["x"].shape[0]),
            "upper_max": float(channel["upper_y"].max()),
            "lower_min": float(channel["lower_y"].min()),
        }
    sparse_summary = None
    if config.include_sparse_residual and "sparse_residual_layer" in manifest.get("metrics", {}):
        sparse = reconstruct_sparse_residual(config.package)
        sparse_summary = {
            "points": int(sparse["indices"].shape[0]),
            "max_abs_delta": float(abs(sparse["delta_y"]).max()) if sparse["delta_y"].size else 0.0,
        }
    noise_summary = None
    if config.include_noise_layer and "noise_layer" in manifest.get("metrics", {}):
        noise = reconstruct_noise_layer(config.package, samples=config.samples)
        noise_summary = {
            "samples": noise.sample_count,
            "max_abs": float(abs(noise.y).max()),
        }
    retained_summary = None
    if config.include_retained:
        retained = reconstruct_retained_signal(config.package, samples=config.samples)
        retained_summary = {
            "samples": retained.sample_count,
            "y_min": float(retained.y.min()),
            "y_max": float(retained.y.max()),
        }
    return {
        "package": str(config.package),
        "manifest": manifest,
        "manifest_warnings": manifest_warnings,
        "reconstructed": _series_summary(reconstructed),
        "retained": retained_summary,
        "channel": channel_summary,
        "sparse_residual": sparse_summary,
        "noise_layer": noise_summary,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vizcompress",
        description="Compress large data into compact visual models.",
    )
    parser.add_argument("--version", action="store_true", help="Print version and exit.")
    subparsers = parser.add_subparsers(dest="command")

    build = subparsers.add_parser("build", help="Build SVG/demo/metrics outputs.")
    input_group = build.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--synthetic", type=int, metavar="N", help="Generate a synthetic time series.")
    input_group.add_argument("--csv", type=Path, help="Read a CSV time series.")
    build.add_argument("--synthetic-kind", choices=SYNTHETIC_KINDS, default="smooth", help="Synthetic dataset shape.")
    build.add_argument("--x-column", default="time", help="CSV x/time column name.")
    build.add_argument("--y-column", default="value", help="CSV y/value column name.")
    build.add_argument("--out", type=Path, default=Path("vizcompress_outputs"), help="Output directory.")
    build.add_argument("--rdp-epsilon", type=float, default=0.012, help="RDP epsilon on normalized y values.")
    build.add_argument("--fourier-terms", type=int, default=96, help="Number of Fourier coefficients to keep.")
    build.add_argument("--svg-samples", type=int, default=2400, help="Number of samples for Fourier SVG realization.")
    build.add_argument("--smooth-window", type=int, default=1, help="Apply moving-average data cleaning before compression.")
    build.add_argument("--sigma-clip", type=float, default=None, help="Clip outliers outside mean +/- K standard deviations.")
    build.add_argument("--noise-layer-terms", type=int, default=0, help="Store raw-minus-cleaned residual as an independent Fourier layer.")
    build.add_argument("--auto-noise-layer", action="store_true", help="Store a Fourier noise layer only when residual analysis recommends it.")
    build.add_argument("--direct-svg", action="store_true", help="Also export a full direct SVG baseline.")
    build.add_argument("--channel", action="store_true", help="Also build a Fourier center plus residual band model.")
    build.add_argument(
        "--channel-band",
        choices=["global_std", "rolling_std"],
        default="rolling_std",
        help="Residual band estimation method.",
    )
    build.add_argument("--channel-window", type=int, default=501, help="Rolling window for channel band estimation.")
    build.add_argument("--channel-k", type=float, default=3.0, help="Standard-deviation multiplier for channel width.")
    build.add_argument("--channel-band-epsilon", type=float, default=0.01, help="RDP epsilon for channel band curve.")
    build.add_argument("--package", action="store_true", help="Also write a .vizasset package directory.")
    build.add_argument(
        "--package-profile",
        choices=["retain-residual", "clean"],
        default="retain-residual",
        help="Package profile: retain residual layers or export only cleaned main signal.",
    )
    build.add_argument("--package-name", default=None, help="Package directory name used with --package.")
    build.add_argument(
        "--x-domain-policy",
        choices=["preserve", "compressed", "auto"],
        default="preserve",
        help="How irregular x domains are stored in packages.",
    )
    build.add_argument("--x-domain-epsilon", type=float, default=0.002, help="RDP epsilon for compressed x-domain delta.")
    build.add_argument("--x-domain-max-error", type=float, default=1e-4, help="Max x error allowed by --x-domain-policy auto.")
    build.add_argument("--review-packet", action="store_true", help="Write a review.json packet for the generated package.")
    build.add_argument(
        "--review-source",
        choices=["model-input", "raw-input"],
        default="model-input",
        help="Source series used for package review packet fidelity checks.",
    )
    build.add_argument("--review-max-rmse", type=float, default=None, help="Review packet RMSE acceptance budget.")
    build.add_argument("--review-max-mae", type=float, default=None, help="Review packet MAE acceptance budget.")
    build.add_argument("--review-max-error", type=float, default=None, help="Review packet max absolute error budget.")
    build.add_argument("--require-review-pass", action="store_true", help="Fail build when the generated review packet is not accepted.")
    build.add_argument(
        "--clean-output",
        action="store_true",
        help="Remove and recreate the output directory before build.",
    )

    mvp = subparsers.add_parser("mvp", help="Run the MVP demo pipeline: build, verify, benchmark, summarize.")
    mvp.add_argument("--samples", type=int, default=20_000, help="Synthetic sample count for the demo asset.")
    mvp.add_argument("--synthetic-kind", choices=SYNTHETIC_KINDS, default="spikes", help="Synthetic dataset shape.")
    mvp.add_argument("--out", type=Path, default=Path("mvp_outputs"), help="MVP output directory.")
    mvp.add_argument("--fourier-terms", type=int, default=64, help="Fourier coefficients for the demo package.")
    mvp.add_argument("--svg-samples", type=int, default=1200, help="Preview SVG sample count.")
    mvp.add_argument("--channel-k", type=float, default=3.0, help="Standard-deviation multiplier for channel width.")
    mvp.add_argument("--channel-window", type=int, default=501, help="Rolling window for channel band estimation.")
    mvp.add_argument("--channel-band-epsilon", type=float, default=0.01, help="RDP epsilon for channel band curve.")
    mvp.add_argument("--rdp-epsilon", type=float, default=0.012, help="RDP epsilon on normalized y values.")
    mvp.add_argument("--review-max-rmse", type=float, default=None, help="Optional review RMSE gate.")
    mvp.add_argument("--review-max-mae", type=float, default=None, help="Optional review MAE gate.")
    mvp.add_argument("--review-max-error", type=float, default=None, help="Optional review max-error gate.")
    mvp.add_argument("--min-fourier-r2", type=float, default=0.95, help="Minimum Fourier R2 expected by the MVP smoke benchmark.")
    mvp.add_argument(
        "--clean-output",
        action="store_true",
        help="Remove and recreate the MVP output directory before running.",
    )

    bench = subparsers.add_parser("bench", help="Benchmark direct SVG size against model-backed package size.")
    bench.add_argument(
        "--synthetic-sizes",
        required=True,
        help="Comma-separated synthetic sample sizes, for example: 1000,10000,100000.",
    )
    bench.add_argument("--out", type=Path, default=Path("benchmark_outputs/size_sweep.json"), help="Benchmark JSON path.")
    bench.add_argument("--report-md", type=Path, default=None, help="Optional Markdown benchmark report path.")
    bench.add_argument(
        "--clean-output",
        action="store_true",
        help="Clean/recreate benchmark output targets before writing.",
    )
    bench.add_argument(
        "--synthetic-kind",
        choices=(*SYNTHETIC_KINDS, "all"),
        default="smooth",
        help="Synthetic dataset shape, or 'all' for a benchmark matrix.",
    )
    bench.add_argument("--rdp-epsilon", type=float, default=0.012, help="RDP epsilon on normalized y values.")
    bench.add_argument("--fourier-terms", type=int, default=96, help="Number of Fourier coefficients to keep.")
    bench.add_argument(
        "--fourier-terms-sweep",
        default=None,
        help="Comma-separated Fourier term counts. Overrides --fourier-terms when set.",
    )
    bench.add_argument("--svg-samples", type=int, default=1200, help="Number of preview SVG samples.")
    bench.add_argument("--smooth-window", type=int, default=1, help="Apply moving-average data cleaning before compression.")
    bench.add_argument("--sigma-clip", type=float, default=None, help="Clip outliers outside mean +/- K standard deviations.")
    bench.add_argument("--noise-layer-terms", type=int, default=0, help="Benchmark a Fourier residual noise layer.")
    bench.add_argument("--auto-noise-layer", action="store_true", help="Benchmark Fourier noise layer only when residual analysis recommends it.")
    bench.add_argument(
        "--x-domain-policy",
        choices=["preserve", "compressed", "auto"],
        default="preserve",
        help="How irregular x domains are stored in packages.",
    )
    bench.add_argument("--x-domain-epsilon", type=float, default=0.002, help="RDP epsilon for compressed x-domain delta.")
    bench.add_argument("--x-domain-max-error", type=float, default=1e-4, help="Max x error allowed by --x-domain-policy auto.")
    bench.add_argument("--channel", action="store_true", help="Benchmark the Fourier channel package.")
    bench.add_argument("--channel-window", type=int, default=501, help="Rolling window for channel band estimation.")
    bench.add_argument("--channel-k", type=float, default=3.0, help="Standard-deviation multiplier for channel width.")
    bench.add_argument("--channel-k-sweep", default=None, help="Comma-separated channel K values. Forces --channel.")
    bench.add_argument("--channel-band-epsilon", type=float, default=0.01, help="RDP epsilon for channel band curve.")
    bench.add_argument("--require-svg-gzip-win", action="store_true", help="Fail when no benchmark row beats SVG.gz size.")
    bench.add_argument("--require-csv-gzip-win", action="store_true", help="Fail when no benchmark row beats source CSV.gz size.")
    bench.add_argument("--min-fourier-r2", type=float, default=None, help="Fail when any benchmark row has lower Fourier R2.")
    bench.add_argument("--min-channel-coverage", type=float, default=None, help="Fail when any benchmark row has lower channel coverage.")
    bench.add_argument(
        "--defensible-channel-coverage",
        type=float,
        default=0.9,
        help="Minimum channel coverage used to pick defensible high-fidelity candidates.",
    )

    inspect = subparsers.add_parser("inspect", help="Inspect a .vizasset package and verify reconstruction.")
    inspect.add_argument("package", type=Path, help=".vizasset package directory.")
    inspect.add_argument("--samples", type=int, default=1200, help="Reconstruction sample count.")

    reconstruct = subparsers.add_parser("reconstruct", help="Reconstruct a .vizasset package and report outputs.")
    reconstruct.add_argument("package", type=Path, help=".vizasset package directory.")
    reconstruct.add_argument("--samples", type=int, default=1200, help="Reconstruction sample count.")
    reconstruct.add_argument(
        "--signal",
        choices=["center", "retained"],
        default="center",
        help="Reconstruction signal to return: center or retained.",
    )
    reconstruct.add_argument(
        "--no-channel",
        dest="include_channel",
        action="store_false",
        help="Skip channel reconstruction details.",
    )
    reconstruct.add_argument(
        "--no-sparse-residual",
        dest="include_sparse_residual",
        action="store_false",
        help="Skip sparse residual reconstruction details.",
    )
    reconstruct.add_argument(
        "--no-noise-layer",
        dest="include_noise_layer",
        action="store_false",
        help="Skip noise-layer reconstruction details.",
    )
    reconstruct.add_argument(
        "--no-retained",
        dest="include_retained",
        action="store_false",
        help="Skip retained reconstruction summary.",
    )

    verify = subparsers.add_parser("verify", help="Validate a .vizasset/.vizretain/.vizclean package.")
    verify.add_argument("package", type=Path, help="Package directory to validate.")
    verify.add_argument("--samples", type=int, default=1024, help="Reconstruction sample count used by validation.")
    verify_source = verify.add_mutually_exclusive_group()
    verify_source.add_argument("--synthetic", type=int, metavar="N", help="Verify decoded package against synthetic source data.")
    verify_source.add_argument("--csv", type=Path, help="Verify decoded package against CSV source data.")
    verify.add_argument("--synthetic-kind", choices=SYNTHETIC_KINDS, default="smooth", help="Synthetic source shape.")
    verify.add_argument("--x-column", default="time", help="CSV x/time column name for source verification.")
    verify.add_argument("--y-column", default="value", help="CSV y/value column name for source verification.")
    verify.add_argument("--signal", choices=["retained", "center"], default="retained", help="Decoded signal to compare with source.")
    verify.add_argument("--max-rmse", type=float, default=None, help="Fail if source RMSE exceeds this budget.")
    verify.add_argument("--max-mae", type=float, default=None, help="Fail if source MAE exceeds this budget.")
    verify.add_argument("--max-error", type=float, default=None, help="Fail if source max absolute error exceeds this budget.")
    verify.add_argument("--max-x-error", type=float, default=1e-9, help="Fail if x-domain max error exceeds this budget.")

    recommend = subparsers.add_parser("recommend", help="Summarize recommendation counts from a benchmark JSON file.")
    recommend.add_argument("benchmark", type=Path, help="Benchmark JSON generated by the bench command.")

    compare = subparsers.add_parser("compare", help="Compare package size against one or more baseline files.")
    compare.add_argument("package", type=Path, help=".vizasset/.vizretain/.vizclean package directory.")
    compare.add_argument("--baseline", action="append", default=[], help="Baseline as name=path. Can be repeated.")

    video_bench = subparsers.add_parser(
        "video-bench",
        help="Benchmark separable spatiotemporal Fourier compression on synthetic video.",
    )
    video_bench.add_argument(
        "--frame-counts",
        required=True,
        help="Comma-separated frame counts, e.g. 120,240,480.",
    )
    video_bench.add_argument("--height", type=int, default=32, help="Frame height.")
    video_bench.add_argument("--width", type=int, default=32, help="Frame width.")
    video_bench.add_argument(
        "--rank-values",
        default="2,4,8",
        help="Comma-separated spatial rank values.",
    )
    video_bench.add_argument(
        "--temporal-terms-values",
        default="8,16,24",
        help="Comma-separated temporal Fourier term values.",
    )
    video_bench.add_argument("--noise-sigma", type=float, default=0.0, help="Noise level of synthetic data.")
    video_bench.add_argument(
        "--baseline-noise-std",
        type=float,
        default=0.0,
        help="Optional noise level for baseline-noise reference.",
    )
    video_bench.add_argument("--out", type=Path, default=Path("benchmark_outputs/video.json"), help="Benchmark JSON path.")
    video_bench.add_argument("--report-md", type=Path, default=None, help="Optional Markdown report path.")
    video_bench.add_argument(
        "--clean-output",
        action="store_true",
        help="Clean/recreate benchmark output targets before writing.",
    )

    precheck = subparsers.add_parser(
        "precheck-benchmarks",
        help="Run benchmark prechecks: field scan + contract validation.",
    )
    precheck.add_argument(
        "--root",
        type=Path,
        default=Path("docs") / "benchmarks",
        help="Benchmark directory.",
    )
    precheck.add_argument(
        "--pattern",
        default="*.json",
        help="File glob pattern for benchmark JSON inputs.",
    )
    precheck.add_argument(
        "--scan-out",
        type=Path,
        default=None,
        help="Path to write scan JSON report.",
    )
    precheck.add_argument(
        "--contract-out",
        type=Path,
        default=None,
        help="Path to write contract validation summary JSON.",
    )
    precheck.add_argument(
        "--skip-scan",
        action="store_true",
        help="Skip structural field scan.",
    )
    precheck.add_argument(
        "--skip-contract",
        action="store_true",
        help="Skip strict contract validation.",
    )
    precheck.add_argument(
        "--fail-on-scan-warning",
        action="store_true",
        help="Fail precheck if scan detects missing/invalid fields.",
    )

    args = parser.parse_args(argv)
    if args.version:
        from vizcompress import __version__

        print(__version__)
        return 0
    if args.command == "build":
        return _build(args)
    if args.command == "mvp":
        return _mvp(args)
    if args.command == "bench":
        return _bench(args)
    if args.command == "inspect":
        return _inspect(args)
    if args.command == "reconstruct":
        return _reconstruct(args)
    if args.command == "verify":
        return _verify(args)
    if args.command == "recommend":
        return _recommend(args)
    if args.command == "compare":
        return _compare(args)
    if args.command == "video-bench":
        return _video_bench(args)
    if args.command == "precheck-benchmarks":
        return _precheck_benchmarks(args)
    parser.print_help()
    return 0


def _precheck_benchmarks(args: argparse.Namespace) -> int:
    root = args.root.expanduser().resolve()
    if args.skip_scan and args.skip_contract:
        print("cannot skip both scan and contract validation")
        return 2
    rc, summary = precheck_benchmarks(
        root=root,
        pattern=args.pattern,
        scan_out=args.scan_out,
        contract_out=args.contract_out,
        skip_scan=args.skip_scan,
        skip_contract=args.skip_contract,
        fail_on_scan_warning=args.fail_on_scan_warning,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return rc


def _build(args: argparse.Namespace) -> int:
    try:
        summary = run_build(
            BuildConfig(
                synthetic=args.synthetic,
                csv=args.csv,
                synthetic_kind=args.synthetic_kind,
                x_column=args.x_column,
                y_column=args.y_column,
                out=args.out,
                rdp_epsilon=args.rdp_epsilon,
                fourier_terms=args.fourier_terms,
                svg_samples=args.svg_samples,
                smooth_window=args.smooth_window,
                sigma_clip=args.sigma_clip,
                noise_layer_terms=args.noise_layer_terms,
                auto_noise_layer=args.auto_noise_layer,
                direct_svg=args.direct_svg,
                channel=args.channel,
                channel_band=args.channel_band,
                channel_window=args.channel_window,
                channel_k=args.channel_k,
                channel_band_epsilon=args.channel_band_epsilon,
                package=args.package,
                package_profile=args.package_profile,
                package_name=args.package_name,
                x_domain_policy=args.x_domain_policy,
                x_domain_epsilon=args.x_domain_epsilon,
                x_domain_max_error=args.x_domain_max_error,
                review_packet=args.review_packet,
                review_source=args.review_source,
                review_max_rmse=args.review_max_rmse,
                review_max_mae=args.review_max_mae,
                review_max_error=args.review_max_error,
                require_review_pass=args.require_review_pass,
                clean_output=args.clean_output,
            )
        )
    except ValueError as exc:
        raise SystemExit(str(exc))
    print(json.dumps(summary, indent=2))
    return 0


def _is_package_output(value: str) -> bool:
    return value.endswith((".vizasset", ".vizretain", ".vizclean"))


def _prepare_output_directory(path: Path, *, clean: bool, label: str) -> Path:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        return path

    if path.is_file():
        if not clean:
            return path
        try:
            _force_remove_file(path)
        except (OSError, PermissionError) as exc:
            raise RuntimeError(
                f"[{label}] cannot replace file output '{path}'. "
                "Close any file handles and rerun with --clean-output, or choose a different --out path."
            ) from exc
        return path

    if not clean:
        return path

    try:
        shutil.rmtree(path)
    except (OSError, PermissionError):
        try:
            _forceful_delete_directory(path)
        except (OSError, PermissionError) as exc:
            fallback = _fallback_output_directory(path, label)
            print(f"[{label}] warning: cannot clean '{path}': {exc}. Using fallback output '{fallback}'.")
            return fallback
    path.mkdir(parents=True, exist_ok=True)
    return path


def _prepare_output_file(path: Path, *, clean: bool, label: str) -> Path:
    if path.exists():
        if path.is_dir():
            if not clean:
                return path
            try:
                shutil.rmtree(path)
            except (OSError, PermissionError) as exc:
                return _fallback_output_file(path, f"{label}-dir", exc)
        else:
            if not clean:
                return path
            try:
                _force_remove_file(path)
            except (OSError, PermissionError) as exc:
                return _fallback_output_file(path, label, exc)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _forceful_delete_directory(path: Path) -> None:
    for child in list(path.iterdir()):
        if child.is_dir() and not child.is_symlink():
            _forceful_delete_directory(child)
        else:
            _force_remove_file(child)
    _set_writable(path)
    path.rmdir()


def _fallback_output_directory(path: Path, label: str) -> Path:
    fallback_name = f"{path.name}.retry_{int(time.time())}"
    return path.with_name(fallback_name)


def _fallback_output_file(path: Path, label: str, exception: BaseException) -> Path:
    fallback_name = f"{path.stem}.retry_{int(time.time())}{path.suffix}"
    fallback = path.with_name(fallback_name)
    print(f"[{label}] warning: cannot clean '{path}' ({exception}). Using fallback output '{fallback}'.")
    return fallback


def _default_package_name(package_profile: str) -> str:
    if package_profile == "clean":
        return "model.vizclean"
    return "model.vizretain"


def _force_remove_file(path: Path) -> None:
    _set_writable(path)
    path.unlink()


def _set_writable(path: Path) -> None:
    try:
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
    except OSError:
        # Proceed with best effort. Exact failure will surface as a precise error.
        pass


def _default_package_name(package_profile: str) -> str:
    if package_profile == "clean":
        return "model.vizclean"
    return "model.vizretain"


def _mvp(args: argparse.Namespace) -> int:
    out_dir: Path = _prepare_output_directory(args.out, clean=args.clean_output, label="mvp")
    build_dir = out_dir / "asset"
    benchmark_json = out_dir / "benchmark.json"
    benchmark_md = out_dir / "benchmark.md"
    summary_json = out_dir / "mvp_summary.json"
    package_dir = build_dir / "model.vizretain"
    out_dir.mkdir(parents=True, exist_ok=True)

    build_args = argparse.Namespace(
        synthetic=args.samples,
        csv=None,
        synthetic_kind=args.synthetic_kind,
        x_column="time",
        y_column="value",
        out=build_dir,
        rdp_epsilon=args.rdp_epsilon,
        fourier_terms=args.fourier_terms,
        svg_samples=args.svg_samples,
        smooth_window=1,
        sigma_clip=None,
        noise_layer_terms=0,
        auto_noise_layer=False,
        direct_svg=True,
        channel=True,
        channel_band="rolling_std",
        channel_window=args.channel_window,
        channel_k=args.channel_k,
        channel_band_epsilon=args.channel_band_epsilon,
        package=True,
        package_profile="retain-residual",
        package_name="model.vizretain",
        x_domain_policy="auto",
        x_domain_epsilon=0.002,
        x_domain_max_error=1e-4,
        review_packet=True,
        review_source="model-input",
        review_max_rmse=args.review_max_rmse,
        review_max_mae=args.review_max_mae,
        review_max_error=args.review_max_error,
        require_review_pass=False,
        clean_output=args.clean_output,
    )
    _build(build_args)

    validation = validate_vizasset(package_dir, reconstruction_samples=min(args.samples, 2048))
    source = make_synthetic_dataset(args.samples, kind=args.synthetic_kind)
    source_validation = validate_vizasset_source(
        package_dir,
        source,
        signal="retained",
        max_rmse=args.review_max_rmse,
        max_mae=args.review_max_mae,
        max_error=args.review_max_error,
    )

    benchmark = benchmark_synthetic_sizes(
        [args.samples],
        synthetic_kind=args.synthetic_kind,
        fourier_terms=args.fourier_terms,
        rdp_epsilon=args.rdp_epsilon,
        svg_samples=args.svg_samples,
        channel=True,
        channel_k=args.channel_k,
        channel_window=args.channel_window,
        channel_band_epsilon=args.channel_band_epsilon,
        x_domain_policy="auto",
        x_domain_epsilon=0.002,
        x_domain_max_error=1e-4,
        defensible_channel_coverage_threshold=0.9,
    )
    gate = evaluate_benchmark_gate(
        benchmark,
        require_svg_gzip_win=False,
        require_csv_gzip_win=False,
        min_fourier_r2=args.min_fourier_r2,
        min_channel_coverage=None,
    )
    benchmark["benchmark_gate"] = gate
    write_benchmark(benchmark_json, benchmark)
    write_benchmark_markdown(benchmark_md, benchmark)

    row = benchmark["rows"][0]
    summary = {
        "mvp": "rrkal.visual_compressor.timeseries",
        "status": "pass" if validation.ok and source_validation.ok and gate["ok"] else "review",
        "synthetic_kind": args.synthetic_kind,
        "samples": args.samples,
        "fourier_terms": args.fourier_terms,
        "outputs": {
            "asset_dir": str(build_dir),
            "package": str(package_dir),
            "benchmark_json": str(benchmark_json),
            "benchmark_md": str(benchmark_md),
            "summary_json": str(summary_json),
        },
        "validation": {
            "package_ok": validation.ok,
            "package_errors": list(validation.errors),
            "source_ok": source_validation.ok,
            "source_errors": list(source_validation.errors),
            "source_metrics": source_validation.details.get("source_verification", {}),
        },
        "benchmark_gate": gate,
        "evidence": {
            "fourier_r2": row["fourier_r2"],
            "package_bytes": row["package_bytes"],
            "direct_svg_gzip_bytes": row["direct_svg_gzip_bytes"],
            "source_csv_gzip_estimated_bytes": row.get("source_csv_gzip_estimated_bytes")
            or row.get("source_csv_gzip_bytes_estimated")
            or row.get("source_csv_gzip_bytes"),
            "direct_svg_gzip_to_package_ratio": row.get("direct_svg_gzip_to_package_ratio"),
            "source_csv_gzip_to_package_ratio": row.get("source_csv_gzip_to_package_ratio"),
            "recommendation": row["recommendation"],
            "gzip_recommendation": row["gzip_recommendation"],
        },
    }
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] == "pass" else 1


def _bench(args: argparse.Namespace) -> int:
    output_json = _prepare_output_file(args.out, clean=args.clean_output, label="bench")
    report_md = None if args.report_md is None else _prepare_output_file(
        args.report_md,
        clean=args.clean_output,
        label="bench-md",
    )

    sample_sizes = parse_sample_sizes(args.synthetic_sizes)
    common = {
        "synthetic_kind": args.synthetic_kind,
        "rdp_epsilon": args.rdp_epsilon,
        "svg_samples": args.svg_samples,
        "channel": args.channel,
        "channel_k": args.channel_k,
        "channel_window": args.channel_window,
        "channel_band_epsilon": args.channel_band_epsilon,
        "smooth_window": args.smooth_window,
        "sigma_clip": args.sigma_clip,
        "noise_layer_terms": args.noise_layer_terms,
        "auto_noise_layer": args.auto_noise_layer,
        "x_domain_policy": args.x_domain_policy,
        "x_domain_epsilon": args.x_domain_epsilon,
        "x_domain_max_error": args.x_domain_max_error,
        "defensible_channel_coverage_threshold": args.defensible_channel_coverage,
    }
    if args.channel_k_sweep and args.fourier_terms_sweep:
        data = benchmark_synthetic_terms_channel_k_sweep(
            sample_sizes,
            fourier_terms_values=parse_fourier_terms(args.fourier_terms_sweep),
            channel_k_values=parse_float_values(args.channel_k_sweep, name="channel K", minimum=0.0),
            rdp_epsilon=args.rdp_epsilon,
            svg_samples=args.svg_samples,
            channel_window=args.channel_window,
            channel_band_epsilon=args.channel_band_epsilon,
            smooth_window=args.smooth_window,
            sigma_clip=args.sigma_clip,
            noise_layer_terms=args.noise_layer_terms,
            auto_noise_layer=args.auto_noise_layer,
            synthetic_kind=args.synthetic_kind,
            x_domain_policy=args.x_domain_policy,
            x_domain_epsilon=args.x_domain_epsilon,
            x_domain_max_error=args.x_domain_max_error,
            defensible_channel_coverage_threshold=args.defensible_channel_coverage,
        )
    elif args.channel_k_sweep:
        data = benchmark_synthetic_channel_k(
            sample_sizes,
            channel_k_values=parse_float_values(args.channel_k_sweep, name="channel K", minimum=0.0),
            fourier_terms=args.fourier_terms,
            rdp_epsilon=args.rdp_epsilon,
            svg_samples=args.svg_samples,
            channel_window=args.channel_window,
            channel_band_epsilon=args.channel_band_epsilon,
            smooth_window=args.smooth_window,
            sigma_clip=args.sigma_clip,
            noise_layer_terms=args.noise_layer_terms,
            auto_noise_layer=args.auto_noise_layer,
            synthetic_kind=args.synthetic_kind,
            x_domain_policy=args.x_domain_policy,
            x_domain_epsilon=args.x_domain_epsilon,
            x_domain_max_error=args.x_domain_max_error,
            defensible_channel_coverage_threshold=args.defensible_channel_coverage,
        )
    elif args.fourier_terms_sweep:
        data = benchmark_synthetic_fourier_terms(
            sample_sizes,
            fourier_terms_values=parse_fourier_terms(args.fourier_terms_sweep),
            **common,
        )
    else:
        data = benchmark_synthetic_sizes(
            sample_sizes,
            fourier_terms=args.fourier_terms,
            **common,
        )
    gate = evaluate_benchmark_gate(
        data,
        require_svg_gzip_win=args.require_svg_gzip_win,
        require_csv_gzip_win=args.require_csv_gzip_win,
        min_fourier_r2=args.min_fourier_r2,
        min_channel_coverage=args.min_channel_coverage,
    )
    if any(
        (
            args.require_svg_gzip_win,
            args.require_csv_gzip_win,
            args.min_fourier_r2 is not None,
            args.min_channel_coverage is not None,
        )
    ):
        data["benchmark_gate"] = gate
    output = write_benchmark(output_json, data)
    data["output"] = str(output)
    if report_md is not None:
        data["markdown_report"] = str(write_benchmark_markdown(report_md, data))
    print(json.dumps(data, indent=2))
    return 0 if gate["ok"] else 1


def _inspect(args: argparse.Namespace) -> int:
    try:
        summary = run_inspect(
            InspectConfig(
                package=args.package,
                samples=args.samples,
            )
        )
    except ValueError as exc:
        raise SystemExit(str(exc))
    print(json.dumps(summary, indent=2))
    return 0


def _reconstruct(args: argparse.Namespace) -> int:
    try:
        summary = run_reconstruct(
            ReconstructConfig(
                package=args.package,
                samples=args.samples,
                signal=args.signal,
                include_channel=args.include_channel,
                include_sparse_residual=args.include_sparse_residual,
                include_noise_layer=args.include_noise_layer,
                include_retained=args.include_retained,
            )
        )
    except ValueError as exc:
        raise SystemExit(str(exc))
    print(json.dumps(summary, indent=2))
    return 0


def _recommend(args: argparse.Namespace) -> int:
    data = json.loads(args.benchmark.read_text(encoding="utf-8"))
    summary = {
        "benchmark": str(args.benchmark),
        "parameters": data.get("parameters", {}),
        "summary": data.get("summary", {}),
        "summary_by_kind": data.get("summary_by_kind", {}),
    }
    print(json.dumps(summary, indent=2))
    return 0


def _verify(args: argparse.Namespace) -> int:
    result = run_verify(
        VerifyConfig(
            package=args.package,
            samples=args.samples,
            synthetic=args.synthetic,
            csv=args.csv,
            synthetic_kind=args.synthetic_kind,
            x_column=args.x_column,
            y_column=args.y_column,
            signal=args.signal,
            max_rmse=args.max_rmse,
            max_mae=args.max_mae,
            max_error=args.max_error,
            max_x_error=args.max_x_error,
        )
    )
    print(json.dumps(result, indent=2))
    return 0 if bool(result.get("ok")) else 1


def _compare(args: argparse.Namespace) -> int:
    baselines = {}
    for item in args.baseline:
        if "=" not in item:
            raise SystemExit(f"--baseline must use name=path syntax: {item}")
        name, value = item.split("=", 1)
        if not name:
            raise SystemExit(f"--baseline name cannot be empty: {item}")
        baselines[name] = Path(value)
    summary = {
        "package": str(args.package),
        "baseline_evidence": baseline_size_summary(args.package, baselines),
    }
    print(json.dumps(summary, indent=2))
    return 0


def _video_bench(args: argparse.Namespace) -> int:
    frame_counts = parse_int_list(args.frame_counts, minimum=2)
    rank_values = parse_int_list(args.rank_values, minimum=1)
    temporal_terms_values = parse_int_list(args.temporal_terms_values, minimum=1)
    if args.height < 1:
        raise ValueError("height must be >= 1")
    if args.width < 1:
        raise ValueError("width must be >= 1")

    output_json = _prepare_output_file(args.out, clean=args.clean_output, label="video-bench")
    report_md = None if args.report_md is None else _prepare_output_file(
        args.report_md,
        clean=args.clean_output,
        label="video-bench-md",
    )

    data = benchmark_video_sweep(
        frame_counts,
        height=args.height,
        width=args.width,
        rank_values=rank_values,
        temporal_terms_values=temporal_terms_values,
        noise_sigma=args.noise_sigma,
        baseline_noise_std=args.baseline_noise_std,
    )
    output = write_video_benchmark(output_json, data)
    data["output"] = str(output)
    if report_md is not None:
        data["markdown_report"] = str(write_video_benchmark_markdown(report_md, data))
    print(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
