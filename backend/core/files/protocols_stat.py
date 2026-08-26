"""SoAI - Core file stat protocols [backend/core/files/protocols_stat.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ("WindowsStatResultProtocol",)


@runtime_checkable
class WindowsStatResultProtocol(Protocol):
    st_file_attributes: int
