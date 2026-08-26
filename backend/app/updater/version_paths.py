"""SoAI - Updater version file path resolution [backend/app/updater/version_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

__all__ = ("resolve_version_py_path",)


def resolve_version_py_path(base_path: str) -> str:
    return os.path.join(base_path, "backend", "core", "meta", "version.py")
