"""SoAI - Core file manager protocols [backend/core/files/protocols_manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

__all__ = ("FileManagerProtocol",)


class FileManagerProtocol(Protocol):
    async def shutdown(self) -> None: ...
