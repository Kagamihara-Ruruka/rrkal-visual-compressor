from __future__ import annotations

import argparse
import fnmatch
import json
import os
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]

DEFAULT_PATTERNS = (
    "tmp_*",
    "tmp-*",
    "smoke*",
    "*smoke*",
    "*model.vizretain*",
    "*retry*",
    "*artifact*",
    "*cleanup*",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan workspace for suspicious temp/ACL-prone output candidates.")
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT_DIR,
        help="Workspace root to scan. Defaults to repository root.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=4,
        help="Maximum traversal depth under root. Default is 4.",
    )
    parser.add_argument(
        "--pattern",
        action="append",
        default=None,
        help="Additional glob pattern to include. Repeatable.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write JSON report to this path (default: stdout).",
    )
    return parser.parse_args()


def _probe_path_access(path: Path) -> dict[str, Any]:
    info = {
        "readable": True,
        "writable": os.access(path, os.W_OK),
        "permission_error": None,
    }

    try:
        iterator = path.iterdir()
        next(iterator, None)
    except PermissionError as exc:
        info.update({"readable": False, "permission_error": str(exc)})
    except OSError as exc:
        info["permission_error"] = str(exc)

    return info


def _matches_patterns(name: str, patterns: tuple[str, ...]) -> list[str]:
    lower = name.lower()
    return [pattern for pattern in patterns if fnmatch.fnmatch(lower, pattern)]


def scan_candidates(root: Path, patterns: tuple[str, ...], max_depth: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    stack: list[tuple[Path, int]] = [(root, 0)]

    while stack:
        path, depth = stack.pop()
        if depth > max_depth:
            continue

        try:
            children = list(path.iterdir())
        except PermissionError as exc:
            if depth == 0 or _matches_patterns(path.name, patterns):
                items.append(
                    {
                        "path": str(path.resolve()),
                        "name": path.name,
                        "depth": depth,
                        "matched_patterns": ["<traversal_permission_denied>"],
                        "readable": False,
                        "writable": os.access(path, os.W_OK),
                        "permission_error": str(exc),
                    }
                )
            continue
        except OSError as exc:
            if depth == 0 or _matches_patterns(path.name, patterns):
                items.append(
                    {
                        "path": str(path.resolve()),
                        "name": path.name,
                        "depth": depth,
                        "matched_patterns": ["<traversal_os_error>"],
                        "readable": False,
                        "writable": os.access(path, os.W_OK),
                        "permission_error": str(exc),
                    }
                )
            continue

        for child in children:
            if not child.is_dir():
                continue

            matched = _matches_patterns(child.name, patterns)
            probe = _probe_path_access(child) if matched else None
            if matched:
                items.append(
                    {
                        "path": str(child.resolve()),
                        "name": child.name,
                        "depth": depth + 1,
                        "matched_patterns": matched,
                        "readable": probe["readable"],
                        "writable": probe["writable"],
                        "permission_error": probe["permission_error"],
                    }
                )

            if depth < max_depth and not (matched and not probe["readable"]):
                stack.append((child, depth + 1))

    return sorted(items, key=lambda item: item["path"].lower())


def build_report(root: Path, patterns: tuple[str, ...], max_depth: int) -> dict[str, Any]:
    candidates = scan_candidates(root, patterns, max_depth)
    blocked = sum(1 for item in candidates if not item["readable"])
    return {
        "schema_version": "1.0",
        "root": str(root.resolve()),
        "max_depth": max_depth,
        "patterns": list(patterns),
        "summary": {
            "total_candidates": len(candidates),
            "permission_blocked": blocked,
        },
        "candidates": candidates,
    }


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve()

    if not root.exists():
        print(f"workspace root does not exist: {root}")
        return 2
    if not root.is_dir():
        print(f"workspace root is not a directory: {root}")
        return 2

    patterns = DEFAULT_PATTERNS
    if args.pattern:
        extra = tuple(pattern.lower() for pattern in args.pattern)
        patterns = tuple(patterns + tuple(f for f in extra if f))

    report = build_report(root, patterns, max_depth=max(args.max_depth, 0))

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        print(f"wrote: {args.out}")
        return 0

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
