from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import os
from pathlib import Path
from typing import Any, Dict


ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_SRC = ROOT_DIR / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


IGNORED_KEYS = {
    "generated_at",
    "generated_at_utc",
    "created_at",
    "host",
    "command",
    "py_project_version",
    "python_version",
    "git_sha",
    "git_rev",
    "generator",
}


def parse_sample_sizes(value: str) -> list[int]:
    sizes = [int(item.strip()) for item in value.split(",") if item.strip()]
    if not sizes:
        raise ValueError("at least one sample size is required")
    return sizes


def parse_float_values(value: str, name: str) -> list[float]:
    values = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            values.append(float(item))
        except ValueError as exc:
            raise ValueError(f"invalid {name}: {item!r}") from exc
    if not values:
        raise ValueError(f"at least one {name} value is required")
    return values


def parse_int_values(value: str, name: str) -> list[int]:
    values = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            values.append(int(item))
        except ValueError as exc:
            raise ValueError(f"invalid {name}: {item!r}") from exc
    if not values:
        raise ValueError(f"at least one {name} value is required")
    return values


def parse_synthetic_kinds(value: str) -> list[str]:
    kinds = [item.strip() for item in value.split(",") if item.strip()]
    if not kinds:
        raise ValueError("at least one synthetic kind is required")
    if "all" in kinds and len(kinds) > 1:
        raise ValueError("'all' cannot be combined with other kinds")
    return kinds


def _run_benchmark(root: Path, args: argparse.Namespace, out_json: Path) -> Path:
    script = root / "scripts" / "run_terms_channel_kind_threshold_sweep.py"
    if not script.exists():
        raise FileNotFoundError(f"benchmark script not found: {script}")

    cmd = [
        sys.executable,
        str(script),
        "--sample-sizes",
        args.sample_sizes,
        "--synthetic-kinds",
        args.synthetic_kinds,
        "--fourier-terms",
        args.fourier_terms,
        "--channel-k",
        args.channel_k,
        "--thresholds",
        args.thresholds,
        "--rdp-epsilon",
        str(args.rdp_epsilon),
        "--svg-samples",
        str(args.svg_samples),
        "--channel-window",
        str(args.channel_window),
        "--channel-band-epsilon",
        str(args.channel_band_epsilon),
        "--smooth-window",
        str(args.smooth_window),
        "--x-domain-policy",
        args.x_domain_policy,
        "--x-domain-epsilon",
        str(args.x_domain_epsilon),
        "--x-domain-max-error",
        str(args.x_domain_max_error),
        "--out-json",
        str(out_json),
        "--out-md",
        str(out_json.with_suffix(".md")),
    ]

    if args.sigma_clip is not None:
        cmd.extend(["--sigma-clip", str(args.sigma_clip)])
    if args.noise_layer_terms:
        cmd.extend(["--noise-layer-terms", str(args.noise_layer_terms)])
    if args.auto_noise_layer:
        cmd.append("--auto-noise-layer")
    if args.require_svg_gzip_win:
        cmd.append("--require-svg-gzip-win")
    if args.require_csv_gzip_win:
        cmd.append("--require-csv-gzip-win")
    if args.min_fourier_r2 is not None:
        cmd.extend(["--min-fourier-r2", str(args.min_fourier_r2)])
    if args.min_channel_coverage is not None:
        cmd.extend(["--min-channel-coverage", str(args.min_channel_coverage)])
    if args.min_defensible_ratio is not None:
        cmd.extend(["--min-defensible-ratio", str(args.min_defensible_ratio)])
    if args.min_high_fidelity_rows is not None:
        cmd.extend(["--min-high-fidelity-rows", str(args.min_high_fidelity_rows)])

    env = os.environ.copy()
    src_path = str(root / "src")
    existing_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(p for p in (src_path, existing_path) if p)

    result = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"benchmark run failed ({root}): {result.returncode}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
    return out_json


def _normalize(payload: Any, precision: int) -> Any:
    if isinstance(payload, float):
        return round(payload, precision)
    if isinstance(payload, int):
        return payload
    if isinstance(payload, str):
        return payload
    if isinstance(payload, list):
        return [_normalize(value, precision) for value in payload]
    if isinstance(payload, dict):
        return {
            key: _normalize(value, precision)
            for key, value in sorted(payload.items())
            if key not in IGNORED_KEYS
        }
    return payload


def _logical_signature(payload: dict[str, Any], precision: int) -> str:
    normalized = _normalize(payload, precision)
    payload_json = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def _compare(left_payload: dict[str, Any], right_payload: dict[str, Any], precision: int) -> bool:
    return _normalize(left_payload, precision) == _normalize(right_payload, precision)


def _safe_load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"benchmark JSON not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_payload(path: Path, payload: dict[str, Any], precision: int) -> dict[str, Any]:
    from vizcompress.benchmark_contracts import validate_benchmark_contract

    ok, errors = validate_benchmark_contract(payload)
    return {
        "path": str(path),
        "passed": ok,
        "error_count": len(errors),
        "precision": precision,
        "errors": errors,
    }


def _build_contract_checks(
    args: argparse.Namespace,
    *,
    left_path: Path,
    left_payload: dict[str, Any],
    right_path: Path,
    right_payload: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    validate_contract = args.validate_contract or args.require_contract_pass
    checks: Dict[str, Any] = {"enabled": validate_contract, "enforced": args.require_contract_pass}

    violations: list[str] = []
    if not validate_contract:
        return checks, violations

    left_contract = _validate_payload(left_path, left_payload, args.precision)
    right_contract = _validate_payload(right_path, right_payload, args.precision)
    checks["left"] = left_contract
    checks["right"] = right_contract
    both_passed = left_contract["passed"] and right_contract["passed"]
    checks["both_passed"] = both_passed
    checks["left_passed"] = bool(left_contract["passed"])
    checks["right_passed"] = bool(right_contract["passed"])

    if not both_passed:
        if not left_contract["passed"]:
            violations.append(f"left_contract_failed: {left_contract['error_count']} errors")
        if not right_contract["passed"]:
            violations.append(f"right_contract_failed: {right_contract['error_count']} errors")

    return checks, violations


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run benchmark sweeps on two roots and compare output parity.")
    parser.add_argument("--left-root", required=True, help="K-side or primary repository path.")
    parser.add_argument("--right-root", required=True, help="C-side or secondary repository path.")
    parser.add_argument("--sample-sizes", default="10000", help="Comma-separated sample counts.")
    parser.add_argument("--synthetic-kinds", default="smooth", help="Comma-separated synthetic kinds.")
    parser.add_argument("--fourier-terms", default="16,32,64", help="Comma-separated Fourier terms.")
    parser.add_argument("--channel-k", default="2,3,4", help="Comma-separated channel K values.")
    parser.add_argument("--thresholds", default="0.90,0.92,0.95,0.98", help="Coverage thresholds.")
    parser.add_argument("--rdp-epsilon", type=float, default=0.6)
    parser.add_argument("--svg-samples", type=int, default=240)
    parser.add_argument("--channel-window", type=int, default=16)
    parser.add_argument("--channel-band-epsilon", type=float, default=0.04)
    parser.add_argument("--smooth-window", type=int, default=1)
    parser.add_argument("--sigma-clip", type=float, default=None)
    parser.add_argument("--noise-layer-terms", type=int, default=0)
    parser.add_argument("--auto-noise-layer", action="store_true")
    parser.add_argument("--left-out-json", default="docs/benchmarks/terms_channel_parity_left.json")
    parser.add_argument("--right-out-json", default="docs/benchmarks/terms_channel_parity_right.json")
    parser.add_argument(
        "--report-json",
        default="docs/benchmarks/terms_channel_benchmark_parity_report.json",
        help="Output path for parity report.",
    )
    parser.add_argument("--x-domain-policy", default="preserve")
    parser.add_argument("--x-domain-epsilon", type=float, default=0.002)
    parser.add_argument("--x-domain-max-error", type=float, default=1e-4)
    parser.add_argument("--require-svg-gzip-win", action="store_true")
    parser.add_argument("--require-csv-gzip-win", action="store_true")
    parser.add_argument("--min-fourier-r2", type=float, default=None)
    parser.add_argument("--min-channel-coverage", type=float, default=None)
    parser.add_argument("--min-defensible-ratio", type=float, default=None)
    parser.add_argument("--min-high-fidelity-rows", type=int, default=None)
    parser.add_argument("--skip-run", action="store_true", help="Use existing --left-out-json and --right-out-json files.")
    parser.add_argument(
        "--validate-contract",
        action="store_true",
        help="Validate benchmark contract constraints for both side payloads before parity comparison.",
    )
    parser.add_argument(
        "--require-contract-pass",
        action="store_true",
        help="Fail command when contract checks fail (implies validate-contract behavior).",
    )
    parser.add_argument("--precision", type=int, default=12, help="Float rounding precision for logical signature.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    left_root = Path(args.left_root).expanduser().resolve()
    right_root = Path(args.right_root).expanduser().resolve()
    left_path = left_root / args.left_out_json
    right_path = right_root / args.right_out_json

    parse_sample_sizes(args.sample_sizes)
    parse_int_values(args.sample_sizes, "sample sizes")
    parse_synthetic_kinds(args.synthetic_kinds)
    parse_float_values(args.fourier_terms.replace(" ", ""), "fourier terms")
    parse_float_values(args.channel_k, "channel k")
    parse_float_values(args.thresholds, "threshold")

    if not args.skip_run:
        left_path = _run_benchmark(left_root, args, left_path)
        right_path = _run_benchmark(right_root, args, right_path)

    left_payload = _safe_load_json(left_path)
    right_payload = _safe_load_json(right_path)

    contract_checks, contract_violations = _build_contract_checks(
        args,
        left_path=left_path,
        left_payload=left_payload,
        right_path=right_path,
        right_payload=right_payload,
    )

    if contract_checks.get("enabled") and contract_checks.get("both_passed") is False:
        print("contract validation failed")
        for side in ("left", "right"):
            side_data = contract_checks.get(side, {})
            if not isinstance(side_data, dict):
                continue
            if side_data.get("passed"):
                continue
            print(f"{side} errors={side_data['error_count']}")
            for item in side_data.get("errors", [])[:3]:
                print(f"  - {item}")

    left_hash = _logical_signature(left_payload, args.precision)
    right_hash = _logical_signature(right_payload, args.precision)

    parity_ok = left_hash == right_hash
    match = _compare(left_payload, right_payload, args.precision)

    report = {
        "left": str(left_path),
        "right": str(right_path),
        "left_hash": left_hash,
        "right_hash": right_hash,
        "logical_signature_match": match,
        "parity_ok": parity_ok,
        "precision": args.precision,
        "skip_run": args.skip_run,
        "contract_validation": contract_checks,
        "contract_violations": contract_violations,
        "status": "ok",
    }

    if contract_violations:
        report["status"] = "contract_failed"
    elif not match:
        report["status"] = "signature_mismatch"
    elif not parity_ok:
        report["status"] = "parity_failed"

    for side, signature in (("left", left_hash), ("right", right_hash)):
        print(f"{side} hash: {signature}")
    print(f"logical_signature: {'PASS' if match else 'FAIL'}")
    print(f"parity: {'PASS' if parity_ok else 'FAIL'}")
    print(f"status: {report['status']}")

    report_path = Path(args.report_json)
    _write_json(report_path, report)
    print(f"wrote {report_path}")

    if contract_violations:
        return 2
    return 0 if match and parity_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
