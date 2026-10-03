"""SoAI - Committed history reset realtime notification [backend/core/history/reset_notification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.events.types_system import HardwareHistoryResetEvent, MetricsHistoryResetEvent
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict

__all__ = (
    "HistoryResetOutcome",
    "publish_committed_history_reset",
)


@dataclass(frozen=True, slots=True)
class HistoryResetOutcome:
    cleared_through_ms: int
    realtime_synced: bool

    def to_response_fields(self) -> JSONDict:
        return {
            "cleared_through_ms": self.cleared_through_ms,
            "realtime_sync": "synced" if self.realtime_synced else "degraded",
        }


async def publish_committed_history_reset(
    *,
    event_bus: EventBusProtocol | None,
    event: MetricsHistoryResetEvent | HardwareHistoryResetEvent,
    logger: LoggerProtocol,
    operation: str,
) -> HistoryResetOutcome:
    if event_bus is None:
        return HistoryResetOutcome(event.cleared_through_ms, realtime_synced=False)
    try:
        await event_bus.publish(event)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        log_exception(
            logger,
            coerce_to_soai_error(exception, operation=operation),
            message="History reset committed, but its realtime notification failed.",
            operation=operation,
            details={"event_type": type(event).__name__},
            level="warning",
        )
        return HistoryResetOutcome(event.cleared_through_ms, realtime_synced=False)
    return HistoryResetOutcome(event.cleared_through_ms, realtime_synced=True)
