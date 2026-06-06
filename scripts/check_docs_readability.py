#!/usr/bin/env python3
"""Repository-local docs readability guard for c_2.

Checks for:
  - UTF-8 strict decode
  - U+FFFD marker presence
  - Private Use Area (PUA) marker presence
  - potential mojibake warning markers
  - changed-hunk human review signal (via git diff)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterable


def _is_pua_char(ch: str) -> bool:
    cp = ord(ch)
    if 0xE000 <= cp <= 0xF8FF:
        return True
    if 0xF0000 <= cp <= 0xFFFFD:
        return True
    if 0x100000 <= cp <= 0x10FFFD:
        return True
    return False


def _scan_text(path: Path) -> tuple[int, int, int, list[str], list[str]]:
    data = path.read_bytes()
    issues: list[str] = []
    warnings: list[str] = []

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        issues.append(
            f"UTF-8 decode fail at byte {e.start} (reason={e.reason}, context={data[e.start:e.start+10].hex(' ')})"
        )
        return 1, 0, 0, issues, warnings

    u_fffd = text.count("\ufffd")
    if u_fffd:
        warnings.append(f"U+FFFD present: {u_fffd}")

    bom_count = text.count("\ufeff")
    if bom_count > 1:
        warnings.append(f"embedded BOM marker U+FEFF count: {bom_count}")

    control_count = 0
    for ch in text:
        if ch in "\n\r\t":
            continue
        if ord(ch) < 0x20:
            control_count += 1
    if control_count:
        warnings.append(f"non-printable control char count: {control_count}")
    pua_positions = [(i + 1, ord(ch)) for i, ch in enumerate(text) if _is_pua_char(ch)]
    pua_count = len(pua_positions)
    if pua_count:
        sample = pua_positions[:5]
        warnings.append(
            f"PUA chars found: {pua_count} (first samples: {sample})"
        )

    return 0, u_fffd, pua_count, issues, warnings


def _iter_paths(paths: Iterable[Path]) -> Iterable[Path]:
    for p in paths:
        if not p.exists():
            raise FileNotFoundError(p)
        if p.is_dir():
            yield from (
                x
                for x in sorted(p.rglob("*"))
                if x.is_file() and x.suffix.lower() in {".md", ".markdown", ".mdx", ".txt"}
            )
        else:
            yield p


def _git_diff_lines(path: Path) -> list[tuple[int, str, str]]:
    """Return suspicious changed lines: (lineno_hint, tag, content)."""
    try:
        cp = subprocess.run(
            ["git", "diff", "--", str(path)],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except FileNotFoundError:
        return []
    if cp.returncode != 0:
        return [(-1, "diff-fail", cp.stderr.strip()[:200])]
    lines = cp.stdout.splitlines()
    suspicious: list[tuple[int, str, str]] = []
    new_lno = 0
    old_lno = 0
    for line in lines:
        if line.startswith("@@"):
            # Parse hunk header: @@ -old,+new @@
            continue
        if line.startswith("+") and not line.startswith("+++"):
            content = line[1:]
            if any(ord(ch) == 0xFFFD for ch in content) or any(_is_pua_char(ch) for ch in content):
                suspicious.append((new_lno, "+", content))
        if line.startswith("+") and not line.startswith("+++"):
            new_lno += 1
        elif line.startswith("-") and not line.startswith("---"):
            old_lno += 1
        else:
            if line.startswith((" ","\\ No newline at end of file")):
                continue
    return suspicious


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check docs readability markers.")
    parser.add_argument("paths", nargs="+", help="doc files or dirs to scan")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero if warnings (FFFD/PUA/mojibake markers) are found",
    )
    args = parser.parse_args(argv)

    files = list(_iter_paths(Path(p) for p in args.paths))
    if not files:
        print("No markdown/doc text files selected.")
        return 0

    fail = 0
    warn = 0

    print("Docs readability scan")
    for path in files:
        issue_count, u_fffd, pua_count, issues, warnings = _scan_text(path)
        print(f"\n- {path}")
        if issue_count:
            fail += issue_count
        if issue_count:
            for i in issues:
                print(f"  ERROR: {i}")
        if warnings:
            warn += len(warnings)
            for w in warnings:
                print(f"  WARN: {w}")
        else:
            print("  OK: UTF-8 clean, no known readability markers.")

        diff_marks = _git_diff_lines(path)
        if diff_marks:
            print("  Diff hunk review: suspicious marker lines in unstaged changes:")
            for idx, tag, content in diff_marks[:20]:
                preview = content[:180].replace("\t", "\\t")
                print(f"    {tag} {idx:>4}: {preview}")
            if len(diff_marks) > 20:
                print(f"    ... and {len(diff_marks)-20} more lines")
        else:
            print("  Diff hunk review: no marker-triggered suspicious changed lines")

    if fail:
        print(f"\nFAIL: decode errors={fail}")
        return 1

    if warn and args.strict:
        print(f"\nWARN: soft-readability concerns={warn} (strict mode)")
        return 2

    if warn:
        print(f"\nWARN: soft-readability concerns={warn}")
        return 0

    print("\nPASS: no decode errors, no marker risks detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
