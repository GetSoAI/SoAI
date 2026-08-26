"""SoAI - File explorer event publishing with non-critical handling [backend/features/file_explorer/event_publishing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.events.types_file_explorer import FileSystemChangedEvent
from core.logging.trace import get_logger

__all__ = ("try_publish_filesystem_event",)

LOGGER_NAME = "SoAI.features.file_explorer.event_publishing"
OPERATION = "file_explorer.publish_filesystem_event"


async def try_publish_filesystem_event(
    event_bus: EventBusProtocol,
    event: FileSystemChangedEvent,
) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        await event_bus.publish(event)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to publish file system change event (non-critical).",
            operation=OPERATION,
            level="debug",
        )
