from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _as_float(value: Any) -> float:
    return float(value)


def round_float(value: Any, precision: int) -> float:
    return round(_as_float(value), precision)


def extract_signature(data: dict[str, Any], precision: int) -> dict[str, Any]:
    signature: dict[str, Any] = {}
    signature["benchmark"] = data.get("benchmark")
    parameters = data.get("parameters", {})
    signature["parameters"] = {
        "sample_sizes": parameters.get("sample_sizes"),
        "synthetic_kinds": parameters.get("synthetic_kinds") or parameters.get("synthetic_kind"),
        "fourier_terms_values": parameters.get("fourier_terms_values"),
        "channel_k_values": parameters.get("channel_k_values"),
        "thresholds": parameters.get("thresholds"),
        "gate_policy": parameters.get("gate_policy"),
    }

    sweep_signature = []
    for row in data.get("sweep", []):
        by_kind = {}
        for kind_name, kind_payload in row.get("rows_by_kind", {}).items():
            by_kind[kind_name] = {
                "high_fidelity_rows_count": int(kind_payload.get("high_fidelity_rows_count", 0)),
                "defensible_rows_count": int(kind_payload.get("defensible_rows_count", 0)),
                "defensible_rows_ratio": round_float(kind_payload.get("defensible_rows_ratio", 0.0), precision),
            }

        best = row.get("global_best_row") or {}
        gate = row.get("benchmark_gate", {})
        sweep_signature.append(
            {
                "threshold": round_float(row.get("threshold", 0.0), precision),
                "high_fidelity_rows_count": int(row.get("high_fidelity_rows_count", 0)),
                "defensible_rows_count": int(row.get("defensible_rows_count", 0)),
                "defensible_rows_ratio": round_float(row.get("defensible_rows_ratio", 0.0), precision),
                "best_ratio": round_float(row.get("best_ratio", 0.0), precision),
                "best_global_samples": row.get("best_global_samples"),
                "best_global_sample_count": row.get("best_global_sample_count"),
                "global_best_row": {
                    "synthetic_kind": best.get("synthetic_kind"),
                    "samples": best.get("samples"),
                    "fourier_terms": best.get("fourier_terms"),
                    "channel_k": best.get("channel_k"),
                    "ratio": round_float(best.get("ratio", 0.0), precision),
                },
                "benchmark_gate": {
                    "ok": gate.get("ok"),
                    "errors": sorted(gate.get("errors", [])),
                },
                "rows_by_kind": by_kind,
            }
        )
    signature["sweep"] = sweep_signature
    return signature


def compare_payload(left: dict[str, Any], right: dict[str, Any], precision: int) -> list[str]:
    diffs = []
    left_sig = extract_signature(left, precision)
    right_sig = extract_signature(right, precision)

    if left_sig.get("benchmark") != right_sig.get("benchmark"):
        diffs.append(f"benchmark mismatch: {left_sig.get('benchmark')} != {right_sig.get('benchmark')}")
    if left_sig.get("parameters") != right_sig.get("parameters"):
        diffs.append("parameters mismatch")
    if len(left_sig.get("sweep", [])) != len(right_sig.get("sweep", [])):
        diffs.append("sweep length mismatch")
    else:
        for idx, (a, b) in enumerate(zip(left_sig["sweep"], right_sig["sweep"])):
            if a.get("threshold") != b.get("threshold"):
                diffs.append(f"sweep[{idx}] threshold mismatch: {a.get('threshold')} != {b.get('threshold')}")
            for key in (
                "high_fidelity_rows_count",
                "defensible_rows_count",
                "defensible_rows_ratio",
                "best_ratio",
                "best_global_samples",
                "best_global_sample_count",
            ):
                if a.get(key) != b.get(key):
                    diffs.append(f"sweep[{idx}] key '{key}' mismatch: {a.get(key)} != {b.get(key)}")
            if a.get("benchmark_gate") != b.get("benchmark_gate"):
                diffs.append(f"sweep[{idx}] benchmark_gate mismatch: {a.get('benchmark_gate')} != {b.get('benchmark_gate')}")
            if a.get("global_best_row") != b.get("global_best_row"):
                diffs.append(f"sweep[{idx}] global_best_row mismatch")
            if a.get("rows_by_kind") != b.get("rows_by_kind"):
                diffs.append(f"sweep[{idx}] rows_by_kind mismatch")
            if diffs and len(diffs) > 20:
                break
    return diffs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare benchmark parity between two JSON outputs.")
    parser.add_argument("--left", required=True, help="First benchmark JSON path")
    parser.add_argument("--right", required=True, help="Second benchmark JSON path")
    parser.add_argument("--precision", type=int, default=9, help="Decimal precision for float comparison")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    left_path = Path(args.left)
    right_path = Path(args.right)

    if not left_path.exists():
        raise FileNotFoundError(f"left benchmark file not found: {left_path}")
    if not right_path.exists():
        raise FileNotFoundError(f"right benchmark file not found: {right_path}")

    left_hash = sha256_file(left_path)
    right_hash = sha256_file(right_path)
    if left_hash == right_hash:
        print("hash: MATCH")
        print(f"sha256={left_hash}")
        return 0

    print("hash: DIFF")
    print(f"left={left_path}: {left_hash}")
    print(f"right={right_path}: {right_hash}")

    left = load_json(str(left_path))
    right = load_json(str(right_path))
    diffs = compare_payload(left, right, args.precision)
    if not diffs:
        print("logical_signature: PASS")
        return 0

    print("logical_signature: FAIL")
    for item in diffs:
        print(item)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
