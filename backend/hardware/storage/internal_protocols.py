"""SoAI - Storage subsystem internal protocols [backend/hardware/storage/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

__all__ = ("ShutilDiskUsageProtocol",)


class ShutilDiskUsageProtocol(Protocol):
    @property
    def total(self) -> int: ...
    @property
    def used(self) -> int: ...
    @property
    def free(self) -> int: ...
