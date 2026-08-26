"""SoAI - Plugin SDK version utilities [backend/plugin_sdk/contracts/version.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.meta.version import __version__

__all__ = ("get_core_version",)


def get_core_version() -> str:
    return __version__
