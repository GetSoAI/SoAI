"""SoAI - MCP worker knowledge attachment events [backend/mcp/worker/knowledge_attachment_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.attachments.attachment_event_payloads import (
    knowledge_attachment_changed_event,
)
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.types.json import JSONDict

__all__ = (
    "publish_worker_knowledge_attachment_changed",
    "publish_worker_knowledge_attachment_changed_noncritical",
    "publish_worker_knowledge_attachment_summaries_noncritical",
)

LOGGER_NAME = "SoAI.mcp.worker.knowledge_attachment_events"


async def publish_worker_knowledge_attachment_changed(
    event_bus: EventBusProtocol,
    *,
    summary: JSONDict,
) -> None:
    await event_bus.publish(knowledge_attachment_changed_event(summary))


async def publish_worker_knowledge_attachment_changed_noncritical(
    event_bus: EventBusProtocol,
    *,
    summary: JSONDict,
    operation: str,
) -> None:
    try:
        await publish_worker_knowledge_attachment_changed(event_bus, summary=summary)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger=get_logger(LOGGER_NAME),
            exception=exception,
            message="Knowledge attachment event publication failed after state update.",
            operation=operation,
            details={"knowledge_attachment_id": summary.get("knowledge_attachment_id")},
            level="warning",
        )


async def publish_worker_knowledge_attachment_summaries_noncritical(
    event_bus: EventBusProtocol,
    *,
    summaries: list[JSONDict],
    operation: str,
) -> None:
    published_ids: set[str] = set()
    for summary in summaries:
        knowledge_attachment_id = summary.get("knowledge_attachment_id")
        if not isinstance(knowledge_attachment_id, str) or knowledge_attachment_id in published_ids:
            continue
        published_ids.add(knowledge_attachment_id)
        await publish_worker_knowledge_attachment_changed_noncritical(
            event_bus,
            summary=summary,
            operation=operation,
        )
