"""SoAI - Core files export protocols [backend/core/files/protocols_export.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

__all__ = ("ExportDatabaseWithCoreProtocol",)


class ExportDatabaseWithCoreProtocol[CoreT](Protocol):
    @property
    def core(self) -> CoreT | None: ...
