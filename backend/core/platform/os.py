"""SoAI - OS detection primitives [backend/core/platform/os.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys

__all__ = (
    "is_linux",
    "is_macos",
    "is_posix",
    "is_windows",
)


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def is_macos() -> bool:
    return sys.platform == "darwin"


def is_posix() -> bool:
    return os.name == "posix"


def is_windows() -> bool:
    return sys.platform.startswith("win")
