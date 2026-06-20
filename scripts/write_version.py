#!/usr/bin/env python3
"""Write version.py from git tag or BOMBS_TRAINING_VERSION."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def resolve_version() -> str:
    env = os.environ.get("BOMBS_TRAINING_VERSION", "").strip()
    if env:
        return env.lstrip("v")
    try:
        described = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            capture_output=True,
            text=True,
            check=True,
            cwd=ROOT,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "dev"
    return described.lstrip("v")


def main() -> int:
    version = resolve_version()
    (ROOT / "version.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
