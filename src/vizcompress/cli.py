from __future__ import annotations

import argparse
import json
from pathlib import Path

from vizcompress.compressors import compress_fourier, compress_fourier_channel, compress_rdp
from vizcompress.core import CompressionReport
from vizcompress.data import make_synthetic_signal, read_csv_timeseries
from vizcompress.exporters import write_channel_svg, write_demo, write_fourier_svg, write_metrics, write_rdp_svg


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
    build.add_argument("--x-column", default="time", help="CSV x/time column name.")
    build.add_argument("--y-column", default="value", help="CSV y/value column name.")
    build.add_argument("--out", type=Path, default=Path("vizcompress_outputs"), help="Output directory.")
    build.add_argument("--rdp-epsilon", type=float, default=0.012, help="RDP epsilon on normalized y values.")
    build.add_argument("--fourier-terms", type=int, default=96, help="Number of Fourier coefficients to keep.")
    build.add_argument("--svg-samples", type=int, default=2400, help="Number of samples for Fourier SVG realization.")
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

    args = parser.parse_args(argv)
    if args.version:
        from vizcompress import __version__

        print(__version__)
        return 0
    if args.command == "build":
        return _build(args)
    parser.print_help()
    return 0


def _build(args: argparse.Namespace) -> int:
    if args.synthetic is not None:
        series = make_synthetic_signal(args.synthetic)
    else:
        series = read_csv_timeseries(args.csv, args.x_column, args.y_column)

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    rdp = compress_rdp(series, args.rdp_epsilon)
    fourier = compress_fourier(series, args.fourier_terms)
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
    report = CompressionReport(input_samples=series.sample_count, rdp=rdp, fourier=fourier, channel=channel)

    rdp_svg = write_rdp_svg(out_dir / "rdp_vectorized.svg", series, rdp)
    fourier_svg = write_fourier_svg(
        out_dir / "fourier_vectorized.svg",
        series,
        fourier,
        args.svg_samples,
    )
    outputs = [rdp_svg.name, fourier_svg.name]
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

    summary = report.as_dict()
    summary["outputs"] = [str(out_dir / name) for name in outputs] + [str(metrics)]
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
