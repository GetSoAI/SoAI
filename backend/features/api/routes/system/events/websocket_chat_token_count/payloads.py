"""SoAI - WebSocket chat token count payload helpers [backend/features/api/routes/system/events/websocket_chat_token_count/payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.openai.token_accounting import build_prompt_occupancy_snapshot
from core.system_api.websocket_payloads import build_websocket_event_payload
from features.api.routes.system.events.chat_stream.command_errors import (
    build_chat_command_error_payload,
)
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes
from features.api.runtime.event_enqueue import enqueue_event_or_warn

if TYPE_CHECKING:
    from core.openai.token_accounting import PromptOccupancy
    from core.types.json import JSONDict
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.streaming.websocket import WebsocketConnection
    from features.openai.model_runtime_profile_resolution import OpenAIModelRuntimeProfile

__all__ = (
    "TokenCountResultDelivery",
    "enqueue_conversation_not_found_token_count_error",
    "enqueue_token_count_profile_result",
    "enqueue_token_count_error",
    "enqueue_token_count_result",
    "token_count_result_delivery",
)


@dataclass(frozen=True, slots=True)
class TokenCountResultDelivery:
    connection: WebsocketConnection
    enqueue_warning_tracker: EnqueueWarningTracker
    conv_id: str
    request_id: str


def token_count_result_delivery(
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    conv_id: str,
    request_id: str,
) -> TokenCountResultDelivery:
    return TokenCountResultDelivery(
        connection=connection,
        enqueue_warning_tracker=enqueue_warning_tracker,
        conv_id=conv_id,
        request_id=request_id,
    )


def _token_count_result_payload(
    *,
    conv_id: str,
    request_id: str,
    occupancy: PromptOccupancy,
    context_window_tokens: int,
    source: str,
    context_window_unverified: bool,
) -> JSONDict:
    return build_websocket_event_payload(
        WebSocketEventTypes.CHAT_TOKEN_COUNT_RESULT,
        {
            "conv_id": conv_id,
            "request_id": request_id,
            "usage_preview": build_prompt_occupancy_snapshot(
                occupancy=occupancy,
                context_window_tokens=context_window_tokens,
                source=source,
                context_window_unverified=context_window_unverified,
            ),
        },
    )


def enqueue_token_count_result(
    *,
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    conv_id: str,
    request_id: str,
    occupancy: PromptOccupancy,
    context_window_tokens: int,
    source: str,
    context_window_unverified: bool,
) -> None:
    payload = _token_count_result_payload(
        conv_id=conv_id,
        request_id=request_id,
        occupancy=occupancy,
        context_window_tokens=context_window_tokens,
        source=source,
        context_window_unverified=context_window_unverified,
    )
    enqueue_event_or_warn(
        enqueue_warning_tracker,
        connection.queue,
        payload,
        "Chat token count result",
    )


def enqueue_token_count_profile_result(
    delivery: TokenCountResultDelivery,
    occupancy: PromptOccupancy,
    runtime_profile: OpenAIModelRuntimeProfile,
    source: str,
) -> None:
    enqueue_token_count_result(
        connection=delivery.connection,
        enqueue_warning_tracker=delivery.enqueue_warning_tracker,
        conv_id=delivery.conv_id,
        request_id=delivery.request_id,
        occupancy=occupancy,
        context_window_tokens=runtime_profile.context_window_tokens,
        source=source,
        context_window_unverified=runtime_profile.context_window_unverified,
    )


async def enqueue_token_count_error(
    *,
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
    conv_id: str,
    request_id: str,
    code: str,
    message: str,
) -> None:
    payload = build_chat_command_error_payload(
        event_type=WebSocketEventTypes.CHAT_TOKEN_COUNT_ERROR,
        conv_id=conv_id,
        request_id=request_id,
        code=code,
        message=message,
        trace_id=trace_id,
        include_trace_id=True,
        include_usage_preview=True,
    )
    enqueue_event_or_warn(
        enqueue_warning_tracker,
        connection.queue,
        payload,
        "Chat token count error",
    )


async def enqueue_conversation_not_found_token_count_error(
    *,
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
    conv_id: str,
    request_id: str,
) -> None:
    await enqueue_token_count_error(
        connection=connection,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
        conv_id=conv_id,
        request_id=request_id,
        code="not_found_error",
        message="Conversation not found.",
    )
