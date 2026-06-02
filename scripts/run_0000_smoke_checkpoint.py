from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from _test_helpers import cli_env


def _select_output_dir(root: Path, requested: str) -> Path:
    base_dir = root / requested
    if not base_dir.exists():
        return base_dir

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    return root / f"{requested}.{timestamp}"


def _run(cli: list[str], cwd: Path | None = None) -> dict[str, Any]:
    cp = subprocess.run(
        [sys.executable, "-m", "vizcompress.cli", *cli],
        env=cli_env(),
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
    )
    payload = None
    try:
        payload = json.loads(cp.stdout) if cp.stdout else None
    except json.JSONDecodeError:
        payload = None
    return {
        "command": " ".join(["python", "-m", "vizcompress.cli", *cli]),
        "returncode": cp.returncode,
        "stdout": cp.stdout,
        "stderr": cp.stderr,
        "json_payload": payload,
    }


def build_report(root: Path, output_dir_name: str) -> dict[str, Any]:
    out_dir = _select_output_dir(root, output_dir_name)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = {
        "schema_version": "1.0",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "commands": {},
        "overall_ok": True,
        "workspace": str(Path.cwd()),
    }

    mvp = out_dir / "mvp"
    mvp_cmd = [
        "mvp",
        "--samples",
        "5000",
        "--synthetic-kind",
        "spikes",
        "--fourier-terms",
        "64",
        "--svg-samples",
        "240",
        "--out",
        str(mvp),
        "--min-fourier-r2",
        "0.95",
    ]
    out["commands"]["mvp"] = _run(mvp_cmd)

    build = out_dir / "build"
    out["commands"]["build"] = _run(
        [
            "build",
            "--synthetic",
            "4000",
            "--synthetic-kind",
            "spikes",
            "--fourier-terms",
            "48",
            "--svg-samples",
            "320",
            "--channel",
            "--auto-noise-layer",
            "--package",
            "--package-name",
            "model.vizretain",
            "--out",
            str(build),
            "--direct-svg",
        ]
    )
    pkg = str(build / "model.vizretain")

    out["commands"]["inspect"] = _run(["inspect", pkg, "--samples", "300"])
    out["commands"]["verify"] = _run(["verify", pkg, "--samples", "300", "--synthetic", "4000", "--synthetic-kind", "spikes"])
    out["commands"]["reconstruct_center"] = _run(["reconstruct", pkg])
    out["commands"]["reconstruct_retained"] = _run(["reconstruct", pkg, "--signal", "retained", "--samples", "128"])
    out["commands"]["compare_direct"] = _run(["compare", pkg, "--baseline", f"direct={build / 'direct.svg'}"])

    bench_out = out_dir / "bench.json"
    out["commands"]["bench"] = _run(
        [
            "bench",
            "--synthetic-sizes",
            "1000",
            "--synthetic-kind",
            "spikes",
            "--fourier-terms",
            "32",
            "--svg-samples",
            "220",
            "--channel",
            "--out",
            str(bench_out),
            "--report-md",
            str(out_dir / "bench.md"),
        ]
    )

    failed: list[str] = [
        key
        for key, payload in out["commands"].items()
        if payload.get("returncode", 1) != 0
    ]
    out["overall_ok"] = len(failed) == 0
    out["failed_commands"] = failed
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a 0000 handoff smoke checkpoint.")
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-dir",
        default="tmp_0000_checkpoint",
        help="Base output directory name under workspace root.",
    )
    parser.add_argument("--report-path", type=Path, default=Path("docs/benchmarks/0000_checkpoint_report.json"))
    args = parser.parse_args()

    workspace_root = args.workspace_root.resolve()
    if not workspace_root.exists():
        print(f"workspace root does not exist: {workspace_root}")
        return 2

    report = build_report(workspace_root, args.output_dir)
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote: {args.report_path}")
    if report["overall_ok"]:
        print("0000 checkpoint: ok")
        return 0
    print(f"0000 checkpoint: failed commands={report['failed_commands']}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
