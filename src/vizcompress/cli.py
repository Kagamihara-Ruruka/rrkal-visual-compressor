from __future__ import annotations

import argparse
import json
from pathlib import Path

from vizcompress.analyzers import analyze_time_series
from vizcompress.benchmarks import benchmark_synthetic_sizes, parse_sample_sizes, write_benchmark
from vizcompress.cleaning import residual_time_series, sigma_clip_time_series, smooth_time_series
from vizcompress.compressors import compress_fourier, compress_fourier_channel, compress_rdp
from vizcompress.core import CompressionReport
from vizcompress.data import SYNTHETIC_KINDS, make_synthetic_dataset, read_csv_timeseries
from vizcompress.exporters import write_channel_svg, write_demo, write_direct_svg, write_fourier_svg, write_metrics, write_rdp_svg
from vizcompress.packages import load_vizasset_manifest, reconstruct_channel, reconstruct_fourier, write_vizasset
from vizcompress.residuals import analyze_residual, compress_sparse_residual


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

    bench = subparsers.add_parser("bench", help="Benchmark direct SVG size against model-backed package size.")
    bench.add_argument(
        "--synthetic-sizes",
        required=True,
        help="Comma-separated synthetic sample sizes, for example: 1000,10000,100000.",
    )
    bench.add_argument("--out", type=Path, default=Path("benchmark_outputs/size_sweep.json"), help="Benchmark JSON path.")
    bench.add_argument(
        "--synthetic-kind",
        choices=(*SYNTHETIC_KINDS, "all"),
        default="smooth",
        help="Synthetic dataset shape, or 'all' for a benchmark matrix.",
    )
    bench.add_argument("--rdp-epsilon", type=float, default=0.012, help="RDP epsilon on normalized y values.")
    bench.add_argument("--fourier-terms", type=int, default=96, help="Number of Fourier coefficients to keep.")
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
    bench.add_argument("--channel-band-epsilon", type=float, default=0.01, help="RDP epsilon for channel band curve.")

    inspect = subparsers.add_parser("inspect", help="Inspect a .vizasset package and verify reconstruction.")
    inspect.add_argument("package", type=Path, help=".vizasset package directory.")
    inspect.add_argument("--samples", type=int, default=1200, help="Reconstruction sample count.")

    recommend = subparsers.add_parser("recommend", help="Summarize recommendation counts from a benchmark JSON file.")
    recommend.add_argument("benchmark", type=Path, help="Benchmark JSON generated by the bench command.")

    args = parser.parse_args(argv)
    if args.version:
        from vizcompress import __version__

        print(__version__)
        return 0
    if args.command == "build":
        return _build(args)
    if args.command == "bench":
        return _bench(args)
    if args.command == "inspect":
        return _inspect(args)
    if args.command == "recommend":
        return _recommend(args)
    parser.print_help()
    return 0


def _build(args: argparse.Namespace) -> int:
    if args.synthetic is not None:
        series = make_synthetic_dataset(args.synthetic, kind=args.synthetic_kind)
    else:
        series = read_csv_timeseries(args.csv, args.x_column, args.y_column)
    raw_series = series
    cleaning_steps = []
    if args.sigma_clip is not None:
        cleaning = sigma_clip_time_series(series, args.sigma_clip)
        cleaning_steps.append(cleaning.metadata())
        series = cleaning.cleaned
    if args.smooth_window > 1:
        cleaning = smooth_time_series(series, args.smooth_window)
        cleaning_steps.append(cleaning.metadata())
        series = cleaning.cleaned

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    rdp = compress_rdp(series, args.rdp_epsilon)
    fourier = compress_fourier(series, args.fourier_terms)
    noise = None
    sparse_residual = None
    residual_profile = None
    if args.noise_layer_terms > 0:
        if not cleaning_steps:
            raise ValueError("--noise-layer-terms requires --sigma-clip or --smooth-window")
        residual = residual_time_series(raw_series, series)
        residual_profile = analyze_residual(raw_series, residual).as_dict()
        noise = compress_fourier(residual, args.noise_layer_terms)
    elif args.auto_noise_layer and cleaning_steps:
        residual = residual_time_series(raw_series, series)
        residual_profile = analyze_residual(raw_series, residual).as_dict()
        if residual_profile["recommended_strategy"] == "fourier_residual_layer":
            noise = compress_fourier(residual, max(16, args.fourier_terms // 2))
        elif residual_profile["recommended_strategy"] == "sparse_outlier_layer":
            sparse_residual = compress_sparse_residual(residual)
    profile = analyze_time_series(series).as_dict()
    if cleaning_steps:
        profile["cleaning"] = cleaning_steps
    channel = None
    if args.channel:
        channel = compress_fourier_channel(
            series,
            args.fourier_terms,
            band_method=args.channel_band,
            window=args.channel_window,
            k=args.channel_k,
            band_epsilon=args.channel_band_epsilon,
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
        args.svg_samples,
    )
    outputs = []
    if args.direct_svg:
        direct_svg = write_direct_svg(out_dir / "direct.svg", series)
        outputs.append(direct_svg.name)
    outputs.extend([rdp_svg.name, fourier_svg.name])
    if channel is not None:
        channel_svg = write_channel_svg(
            out_dir / "fourier_channel.svg",
            series,
            channel,
            args.svg_samples,
        )
        outputs.append(channel_svg.name)
    demo = write_demo(out_dir / "demo.py", series.sample_count, args.fourier_terms)
    outputs.append(demo.name)
    metrics = write_metrics(
        out_dir / "metrics.json",
        report,
        [*outputs, "metrics.json"],
    )
    if args.package:
        package_report = report
        if args.package_profile == "clean":
            package_report = CompressionReport(
                input_samples=report.input_samples,
                rdp=report.rdp,
                fourier=report.fourier,
                channel=report.channel,
                input_profile=report.input_profile,
                residual_profile=report.residual_profile,
            )
        preview = out_dir / ("fourier_channel.svg" if channel is not None else "fourier_vectorized.svg")
        package_name = args.package_name or _default_package_name(args.package_profile)
        package = write_vizasset(
            out_dir / package_name,
            series=series,
            report=package_report,
            preview_svg=preview,
            metrics_json=metrics,
            demo_py=demo,
            package_profile=args.package_profile,
            x_domain_policy=args.x_domain_policy,
            x_domain_epsilon=args.x_domain_epsilon,
            x_domain_max_error=args.x_domain_max_error,
        )
        outputs.append(str(package))

    summary = report.as_dict()
    rendered_outputs = [
        str(name) if _is_package_output(str(name)) else str(out_dir / name)
        for name in outputs
    ]
    summary["outputs"] = rendered_outputs + [str(metrics)]
    print(json.dumps(summary, indent=2))
    return 0


def _is_package_output(value: str) -> bool:
    return value.endswith((".vizasset", ".vizretain", ".vizclean"))


def _default_package_name(package_profile: str) -> str:
    if package_profile == "clean":
        return "model.vizclean"
    return "model.vizretain"


def _bench(args: argparse.Namespace) -> int:
    data = benchmark_synthetic_sizes(
        parse_sample_sizes(args.synthetic_sizes),
        synthetic_kind=args.synthetic_kind,
        fourier_terms=args.fourier_terms,
        rdp_epsilon=args.rdp_epsilon,
        svg_samples=args.svg_samples,
        channel=args.channel,
        channel_k=args.channel_k,
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
    output = write_benchmark(args.out, data)
    data["output"] = str(output)
    print(json.dumps(data, indent=2))
    return 0


def _inspect(args: argparse.Namespace) -> int:
    manifest = load_vizasset_manifest(args.package)
    reconstructed = reconstruct_fourier(args.package, samples=args.samples)
    has_channel = manifest["model"]["primary_method"] == "fourier_channel"
    channel_summary = None
    if has_channel:
        channel = reconstruct_channel(args.package, samples=args.samples)
        channel_summary = {
            "samples": int(channel["x"].shape[0]),
            "upper_max": float(channel["upper_y"].max()),
            "lower_min": float(channel["lower_y"].min()),
        }
    summary = {
        "package": str(args.package),
        "asset_type": manifest["asset_type"],
        "schema_version": manifest["schema_version"],
        "package_profile": manifest.get("package_profile", "unknown"),
        "source": manifest["source"],
        "primary_method": manifest["model"]["primary_method"],
        "contains_noise_layer": "noise_layer" in manifest.get("metrics", {}),
        "contains_sparse_residual_layer": "sparse_residual_layer" in manifest.get("metrics", {}),
        "reconstructed": {
            "samples": reconstructed.sample_count,
            "x_min": float(reconstructed.x.min()),
            "x_max": float(reconstructed.x.max()),
            "y_min": float(reconstructed.y.min()),
            "y_max": float(reconstructed.y.max()),
        },
        "channel": channel_summary,
        "files": manifest["files"],
    }
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


if __name__ == "__main__":
    raise SystemExit(main())
