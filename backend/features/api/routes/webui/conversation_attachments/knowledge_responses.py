"""SoAI - WebUI knowledge attachment response publication [backend/features/api/routes/webui/conversation_attachments/knowledge_responses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.responses import JSONResponse, Response

from features.api.routes.webui.conversation_attachments.events import (
    publish_knowledge_attachment_changed,
)

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.types.json import JSONDict

__all__ = ("knowledge_attachment_summary_response",)


async def knowledge_attachment_summary_response(
    event_bus: EventBusProtocol,
    *,
    summary: JSONDict,
) -> Response:
    await publish_knowledge_attachment_changed(event_bus, summary=summary)
    return JSONResponse(content=summary)
