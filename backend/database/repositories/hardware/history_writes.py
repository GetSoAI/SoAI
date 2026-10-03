"""SoAI - Reset-fenced hardware history writes [backend/database/repositories/hardware/history_writes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from database.repositories.hardware.history_reset import sync_clear_hardware_history
from database.repositories.hardware.logging import (
    resolve_hardware_sample_timestamp_ms,
    sync_log_hardware_metrics,
)

if TYPE_CHECKING:
    from core.database.protocols import DatabaseCoreProtocol
    from core.types.json import JSONDict

__all__ = ("HardwareHistoryWrites",)


class HardwareHistoryWrites:
    def __init__(self, core: DatabaseCoreProtocol) -> None:
        self._core = core
        self._lock = asyncio.Lock()
        self._cleared_through_ms = 0

    async def log(self, info: JSONDict) -> None:
        observed_at_ms = resolve_hardware_sample_timestamp_ms(info)
        async with self._lock:
            if observed_at_ms <= self._cleared_through_ms:
                return
            await self._core.writer.queue_write_operation(
                sync_log_hardware_metrics,
                {**info, "timestamp_ms": observed_at_ms},
            )

    async def clear(self, reset_genesis_uptime: bool) -> int:
        async with self._lock:
            cleared_through_ms = await self._core.writer.queue_write_operation(
                sync_clear_hardware_history,
                reset_genesis_uptime,
            )
            self._cleared_through_ms = max(self._cleared_through_ms, cleared_through_ms)
        return cleared_through_ms
