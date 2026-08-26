"""SoAI - WebUI conversation attachment event publication [backend/features/api/routes/webui/conversation_attachments/events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.attachments.attachment_event_payloads import (
    conversation_attachment_changed_event,
    knowledge_attachment_changed_event,
)

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.types.json import JSONDict

__all__ = (
    "publish_knowledge_attachment_changed",
    "publish_physical_attachment_changed",
    "publish_unique_knowledge_attachment_summaries",
)


async def publish_physical_attachment_changed(
    event_bus: EventBusProtocol,
    *,
    attachment: JSONDict,
) -> None:
    await event_bus.publish(conversation_attachment_changed_event(attachment))


async def publish_knowledge_attachment_changed(
    event_bus: EventBusProtocol,
    *,
    summary: JSONDict,
) -> None:
    await event_bus.publish(knowledge_attachment_changed_event(summary))


async def publish_unique_knowledge_attachment_summaries(
    event_bus: EventBusProtocol,
    *,
    summaries: list[JSONDict],
) -> None:
    published_ids: set[str] = set()
    for summary in summaries:
        knowledge_attachment_id = summary.get("knowledge_attachment_id")
        if not isinstance(knowledge_attachment_id, str) or knowledge_attachment_id in published_ids:
            continue
        published_ids.add(knowledge_attachment_id)
        await publish_knowledge_attachment_changed(event_bus, summary=summary)
