"""SoAI - Backup service protocols [backend/core/backup/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

__all__ = ("ByteHasherProtocol",)


class ByteHasherProtocol(Protocol):
    def update(self, data: bytes | bytearray | memoryview, /) -> None: ...
