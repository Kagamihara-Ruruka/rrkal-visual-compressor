from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import time
from pathlib import Path
from typing import Any

import report_workspace_candidates as scanner


RETRYABLE_WINERRORS = {5, 145, 32}
RETRY_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 0.25


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create cleanup plan for workspace temp/artifact candidates and optionally execute"
            " removals with safety-first behavior."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=scanner.ROOT_DIR,
        help="Workspace root to scan. Defaults to repository root.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=3,
        help="Maximum traversal depth under root. Default is 3.",
    )
    parser.add_argument(
        "--pattern",
        action="append",
        default=None,
        help="Additional glob pattern to include. Repeatable.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually remove selected directories. Default is dry-run.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write report JSON to this path (default: stdout).",
    )
    return parser.parse_args()


def _classify_candidate(candidate: dict[str, Any]) -> str:
    path_name = candidate["name"].lower()
    matched_patterns = set(pattern.lower() for pattern in candidate.get("matched_patterns", ()))
    readable = bool(candidate.get("readable", False))
    writable = bool(candidate.get("writable", False))

    if "*model.vizretain*" in matched_patterns or path_name == "model.vizretain":
        if not readable:
            return "manual_unlock"
        if not writable:
            return "permission_blocked"
        return "skip"

    if not readable:
        return "permission_blocked"
    if candidate.get("depth", 0) == 0:
        return "skip"
    return "candidate"


def _has_retryable_access_error(exc: Exception) -> bool:
    message = str(exc)
    winerror = getattr(exc, "winerror", None)
    if winerror in RETRYABLE_WINERRORS:
        return True
    return "WinError 5" in message or "WinError 145" in message or "Access is denied" in message


def _mark_writable(path: Path) -> None:
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        return


def _fix_locked_paths(path: Path) -> None:
    # Best-effort cleanup pass: clear common read-only attributes on child nodes so
    # a second rmtree attempt has a chance to proceed.
    if not path.exists():
        return

    for child in sorted(path.rglob("*"), reverse=True):
        if not child.exists():
            continue
        _mark_writable(child)

    _mark_writable(path)


def _delete_dir(path: Path, execute: bool) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"

    if not execute:
        return True, "dry_run"

    last_error: Exception | None = None
    for attempt in range(RETRY_ATTEMPTS + 1):
        if attempt > 0:
            _fix_locked_paths(path)
            time.sleep(RETRY_DELAY_SECONDS * attempt)

        try:
            shutil.rmtree(path)
            return True, "deleted"
        except FileNotFoundError:
            return False, "missing"
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if _has_retryable_access_error(exc) and attempt < RETRY_ATTEMPTS:
                continue
            break

    if last_error is None:
        return False, "unknown_error"

    if isinstance(last_error, PermissionError) and _has_retryable_access_error(last_error):
        return False, f"manual_unlock_required: {last_error}"

    if isinstance(last_error, OSError) and _has_retryable_access_error(last_error):
        return False, f"manual_unlock_required: {last_error}"

    return False, f"os_error: {last_error}"


def _run_cleanup(root: Path, max_depth: int, patterns: tuple[str, ...], execute: bool) -> dict[str, Any]:
    candidates = scanner.scan_candidates(root, patterns, max_depth)
    cleanup_items = []

    summary = {
        "dry_run": not execute,
        "total_candidates": len(candidates),
        "to_remove": 0,
        "skipped": 0,
        "deleted": 0,
        "failed": 0,
        "manual_unlock": 0,
    }

    for candidate in candidates:
        decision = _classify_candidate(candidate)

        if decision == "candidate":
            path = Path(candidate["path"])
            ok, detail = _delete_dir(path, execute)
            status = "deleted" if ok and execute else "planned"
            if detail == "dry_run":
                status = "planned"
            elif detail.startswith("manual_unlock_required"):
                status = "manual_unlock"
                summary["manual_unlock"] += 1
            elif not ok:
                status = "failed"
                summary["failed"] += 1
            else:
                summary["deleted"] += 1

            summary["to_remove"] += 1
            cleanup_items.append(
                {
                    "path": candidate["path"],
                    "depth": candidate["depth"],
                    "name": candidate["name"],
                    "matched_patterns": candidate["matched_patterns"],
                    "readable": candidate["readable"],
                    "writable": candidate["writable"],
                    "decision": decision,
                    "status": status,
                    "detail": detail,
                }
            )
            continue

        if decision == "manual_unlock":
            summary["manual_unlock"] += 1

        summary["skipped"] += 1
        cleanup_items.append(
            {
                "path": candidate["path"],
                "depth": candidate["depth"],
                "name": candidate["name"],
                "matched_patterns": candidate["matched_patterns"],
                "readable": candidate["readable"],
                "writable": candidate["writable"],
                "decision": decision,
                "status": "skipped",
                "detail": candidate.get("permission_error") or "skip_by_policy",
            }
        )

    return {
        "schema_version": "1.0",
        "command": "scripts/cleanup_workspace_outputs.py",
        "root": str(root.resolve()),
        "max_depth": max_depth,
        "patterns": list(patterns),
        "summary": summary,
        "cleanup_items": cleanup_items,
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

    patterns = scanner.DEFAULT_PATTERNS
    if args.pattern:
        extra = tuple(pattern.lower() for pattern in args.pattern)
        patterns = tuple(patterns + tuple(f for f in extra if f))

    report = _run_cleanup(root, max_depth=max(args.max_depth, 0), patterns=patterns, execute=args.execute)

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        print(f"wrote: {args.out}")
        return 0

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
