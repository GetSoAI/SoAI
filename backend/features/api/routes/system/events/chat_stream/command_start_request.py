"""SoAI - Request parsing and authorization for chat stream start [backend/features/api/routes/system/events/chat_stream/command_start_request.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.conversations.assistant_turn_variant_identity import (
    require_chat_stream_start_identity,
)
from core.errors.exceptions import ValidationError
from features.api.routes.system.events.chat_stream.command_errors import (
    enqueue_chat_stream_start_error,
)
from features.api.routes.system.events.chat_stream.command_payload_parsing import (
    connection_has_chat_command_access,
    extract_chat_command_payload_hints,
    parse_chat_command_request_fields,
)
from features.api.routes.system.events.chat_stream.start_command_invalid_request_reporting import (
    report_invalid_start_payload,
)
from features.api.runtime.content_preview_feedback import (
    parse_content_preview_feedback,
)
from features.api.runtime.preview_contract_feedback import (
    parse_preview_contract_feedback,
)

if TYPE_CHECKING:
    from core.conversations.assistant_turn_variant_identity import (
        AssistantTurnVariantIdentity,
    )
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict
    from features.api.runtime.content_preview_feedback import ContentPreviewFeedback
    from features.api.runtime.preview_contract_persisted_feedback import (
        PreviewContractFeedback,
    )
    from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "ChatStreamStartRequest",
    "parse_chat_stream_start_request",
)


@dataclass(frozen=True, slots=True)
class ChatStreamStartRequest:
    conv_id: str
    request_id: str
    identity: AssistantTurnVariantIdentity
    openai_request: JSONDict
    content_preview_feedback: ContentPreviewFeedback | None
    preview_contract_feedback: PreviewContractFeedback | None


async def parse_chat_stream_start_request(
    *,
    data: JSONDict,
    connection: WebsocketConnection,
    logger: LoggerProtocol,
    trace_id: str | None,
) -> ChatStreamStartRequest | None:
    hints = extract_chat_command_payload_hints(data)
    if not connection_has_chat_command_access(connection):
        await enqueue_chat_stream_start_error(
            connection,
            hints.conv_id,
            hints.request_id,
            "forbidden_error",
            "Insufficient permissions.",
        )
        return None
    try:
        fields = parse_chat_command_request_fields(data)
        identity = require_chat_stream_start_identity(
            assistant_at_ms=data.get("assistant_at_ms"),
            assistant_turn_at_ms=data.get("assistant_turn_at_ms"),
            model_variant_index=data.get("model_variant_index"),
        )
        content_preview_feedback = parse_content_preview_feedback(data)
        preview_contract_feedback = parse_preview_contract_feedback(data)
    except ValidationError as exception:
        await report_invalid_start_payload(
            connection=connection,
            conv_id=hints.conv_id,
            request_id=hints.request_id,
            logger=logger,
            trace_id=trace_id,
            exception=exception,
        )
        return None
    return ChatStreamStartRequest(
        conv_id=fields.conv_id,
        request_id=fields.request_id,
        identity=identity,
        openai_request=fields.openai_request,
        content_preview_feedback=content_preview_feedback,
        preview_contract_feedback=preview_contract_feedback,
    )
