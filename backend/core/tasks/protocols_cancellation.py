"""SoAI - Cancellation system protocol definitions [backend/core/tasks/protocols_cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from core.tasks.cancellation_types import (
    CancelAllResult,
    HistorySnapshot,
    RecordCancellationResult,
    SweepResult,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "CancellationCoordinatorProtocol",
    "CancellationHistoryProtocol",
)


class CancellationHistoryProtocol(Protocol):
    @property
    def history_limit(self) -> int: ...

    async def record_cancellation(
        self,
        cancellation_id: str,
        reason: str,
        *,
        active_scopes: set[str] | None = None,
    ) -> RecordCancellationResult: ...

    async def is_cancelled(self, cancellation_id: str) -> bool: ...

    async def get_reason(self, cancellation_id: str) -> str | None: ...

    async def check_publish_rate_limit(
        self,
        cancellation_id: str,
        *,
        min_interval: float,
    ) -> bool: ...

    async def clear_scope(self, cancellation_id: str) -> bool: ...

    async def clear_all(self) -> None: ...

    async def get_snapshot(self) -> HistorySnapshot: ...

    async def update_limit(
        self,
        max_history: int,
        *,
        active_scopes: set[str] | None = None,
    ) -> None: ...

    async def has_entries(self) -> bool: ...


class CancellationCoordinatorProtocol(Protocol):
    async def cancel_scope(self, cancellation_id: str, reason: str) -> bool: ...

    async def cancel_all_scopes(
        self,
        reason: str,
        *,
        include_internal: bool,
        exclude_cancellation_ids: tuple[str, ...] = (),
        wait_for_release_timeout: float | None = None,
    ) -> CancelAllResult: ...

    async def clear_scope(self, cancellation_id: str) -> None: ...

    async def reset_all(self) -> None: ...

    async def get_snapshot(self) -> JSONDict: ...

    async def sweep(self) -> SweepResult: ...
