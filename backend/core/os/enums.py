"""SoAI - OS mode enums [backend/core/os/enums.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from enum import Enum

__all__ = ("OSMode",)


class OSMode(str, Enum):
    STANDARD = "standard"
    SOAI_OS = "soai_os"
