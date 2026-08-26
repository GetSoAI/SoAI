"""SoAI - NVIDIA Linux path resolvers [backend/hardware/vendors/nvidia/paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from os import sep

__all__ = ("nvidia_xorg_config_path",)


def nvidia_xorg_config_path() -> str:
    return f"{sep}etc{sep}X11{sep}xorg.conf"
