from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
PROJECT_SRC = str(ROOT_DIR / "src")


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
    current_pythonpath = env.get("PYTHONPATH", "")
    if PROJECT_SRC not in current_pythonpath.split(os.pathsep):
        if current_pythonpath:
            env["PYTHONPATH"] = os.pathsep.join([PROJECT_SRC, current_pythonpath])
        else:
            env["PYTHONPATH"] = PROJECT_SRC
    if extra_env:
        env = {**env, **extra_env}
    return env


def run_cli(args: list[str], **kwargs: object) -> subprocess.CompletedProcess:
    merged_env = kwargs.pop("env", None)
    return subprocess.run(args, env=cli_env(merged_env), **kwargs)
