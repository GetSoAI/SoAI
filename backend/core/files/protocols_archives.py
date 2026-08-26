"""SoAI - Core files archive protocols [backend/core/files/protocols_archives.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

__all__ = (
    "RarArchiveMemberProtocol",
    "RarFileProtocol",
)


@runtime_checkable
class RarArchiveMemberProtocol(Protocol):
    file_redir: tuple[int, int, str] | None
    file_size: int | None
    filename: str | None
    is_symlink: bool | Callable[[], bool] | None

    def isdir(self) -> bool: ...


@runtime_checkable
class RarFileProtocol(Protocol):
    def infolist(self) -> list[RarArchiveMemberProtocol]: ...

    def extract(self, member: RarArchiveMemberProtocol, path: str) -> None: ...

    def close(self) -> None: ...
