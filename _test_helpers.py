from __future__ import annotations

import os
import subprocess
from collections import OrderedDict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if (Path.cwd() / "src" / "vizcompress").exists():
    ROOT_DIR = Path.cwd()
PROJECT_SRC = str(ROOT_DIR / "src")
ROOT_DIR_STR = str(ROOT_DIR)


def _normalize_path(path: str) -> str:
    try:
        return str(Path(path).resolve())
    except OSError:
        return str(Path(path))


def _dedupe_paths(paths: list[str]) -> list[str]:
    deduped: "OrderedDict[str, str]" = OrderedDict()
    for path in paths:
        if not path:
            continue
        normalized = _normalize_path(path).lower()
        if normalized in deduped:
            continue
        deduped[normalized] = path
    return list(deduped.values())


def _is_repo_source(path: str) -> bool:
    try:
        resolved = Path(path).resolve()
    except OSError:
        return False

    if str(resolved).lower() == ROOT_DIR_STR.lower():
        return False

    normalized_path = resolved.as_posix().lower()
    if "rrkal-visual-compressor" not in normalized_path:
        return False

    if resolved.name == "src":
        return resolved != Path(PROJECT_SRC).resolve()

    has_src_package = (resolved / "src" / "vizcompress").exists()
    has_shim_package = (resolved / "vizcompress").exists()
    if has_src_package and has_shim_package:
        return True

    if resolved == Path(PROJECT_SRC).resolve():
        return False

    return False


def script_path(filename: str) -> Path:
    cwd_root = Path.cwd() / "scripts" / filename
    if cwd_root.exists():
        return cwd_root
    return ROOT_DIR / "scripts" / filename


def script_path_str(filename: str) -> str:
    return str(script_path(filename))


def precheck_script() -> str:
    return script_path_str("precheck_benchmarks.py")


def cli_env(extra_env: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()

    current_pythonpath = [
        p
        for p in env.get("PYTHONPATH", "").split(os.pathsep)
        if p
    ]
    filtered = [p for p in current_pythonpath if not _is_repo_source(p)]

    pythonpath_entries: list[str] = [PROJECT_SRC, ROOT_DIR_STR]
    for path in filtered:
        normalized = _normalize_path(path)
        if normalized not in pythonpath_entries:
            pythonpath_entries.append(path)

    env["PYTHONPATH"] = os.pathsep.join(_dedupe_paths(pythonpath_entries))
    if extra_env:
        env = {**env, **extra_env}
    return env


def run_cli(args: list[str], **kwargs: object) -> subprocess.CompletedProcess:
    merged_env = kwargs.pop("env", None)
    return subprocess.run(args, env=cli_env(merged_env), **kwargs)
