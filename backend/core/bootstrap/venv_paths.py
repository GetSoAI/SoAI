"""SoAI - Virtual environment path utilities (stdlib-only) [backend/core/bootstrap/venv_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sysconfig

__all__ = (
    "get_venv_path",
    "get_venv_python_executable",
    "get_venv_site_package_paths",
)

SOAI_VENV_DIR_NAME = "soai_main_venv"
SOAI_VENV_PATH_ENV = "SOAI_VENV_PATH"


def get_venv_path(repo_root_path: str) -> str:
    override = os.environ.get(SOAI_VENV_PATH_ENV, "").strip()
    if override:
        if not os.path.isabs(override):
            override = os.path.join(repo_root_path, override)
        return os.path.abspath(override)
    return os.path.abspath(os.path.join(repo_root_path, SOAI_VENV_DIR_NAME))


def get_venv_python_executable(venv_path: str) -> str:
    if os.name == "nt":
        return os.path.join(venv_path, "Scripts", "python.exe")
    return os.path.join(venv_path, "bin", "python")


def get_venv_site_package_paths(venv_path: str) -> tuple[str, ...]:
    variables = {"base": venv_path, "platbase": venv_path}
    return tuple(
        dict.fromkeys(
            os.path.abspath(sysconfig.get_path(name, vars=variables))
            for name in ("purelib", "platlib")
        )
    )
