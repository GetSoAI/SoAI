"""SoAI - Plugin task progress callback protocol [backend/plugins/protocols_internal/task_progress/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, overload

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("TaskProgressSenderProtocol",)


class TaskProgressSenderProtocol(Protocol):
    @overload
    async def __call__(self, percent: int, message: str) -> None: ...

    @overload
    async def __call__(self, percent: int, message: str, details: JSONValue | None) -> None: ...
