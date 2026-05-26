from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vizcompress",
        description="Compress large data into compact visual models.",
    )
    parser.add_argument("--version", action="store_true", help="Print version and exit.")
    args = parser.parse_args(argv)
    if args.version:
        from vizcompress import __version__

        print(__version__)
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
