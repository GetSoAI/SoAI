"""SoAI - Managed Python dependency bootstrap CLI [backend/core/bootstrap/python_dependencies_cli.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import subprocess
import sys

from core.bootstrap.launch_console import emit
from core.bootstrap.python_dependencies import bootstrap_python_dependencies_if_needed
from core.errors.exceptions import StateError

__all__ = ("main",)


def main() -> None:
    repo_root_path = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.getcwd()
    offline_mode = _read_offline_mode_override()
    try:
        changed = bootstrap_python_dependencies_if_needed(
            repo_root_path,
            offline_mode=offline_mode,
        )
    except (
        OSError,
        StateError,
        ValueError,
        subprocess.CalledProcessError,
    ) as exception:
        emit("ERROR", f"FATAL: Python dependency bootstrap failed: {exception}")
        raise StateError("Python dependency bootstrap failed.") from exception
    if changed:
        emit("INFO", "SoAI Python runtime dependencies are ready.")


def _read_offline_mode_override() -> bool | None:
    raw_value = os.environ.get("SOAI_STAGE0_OFFLINE_MODE", "").strip()
    if raw_value == "1":
        return True
    if raw_value == "0":
        return False
    return None


if __name__ == "__main__":
    main()
