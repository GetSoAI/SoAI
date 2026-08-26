"""SoAI - WebSocket live resource interest subscriptions [backend/features/api/routes/system/events/websocket_resource_interests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.events.protocols import EventBusProtocol
from core.events.types_base import Event
from core.logging.trace import get_logger
from core.system_api.websocket_payloads import build_websocket_event_payload
from core.types.json import JSONDict, JSONValue, is_str_list
from core.validation.integers import is_strict_int
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes
from features.api.routes.system.events.websocket_chat_presentation_interest import (
    chat_presentation_conversation_is_visible,
    normalize_chat_presentation_selector,
)
from features.api.routes.system.events.websocket_errors import enqueue_websocket_error
from features.api.routes.system.events.websocket_event_context import (
    WebsocketEventRuntimeContext,
)
from features.api.routes.system.events.websocket_resource_registry import (
    RESOURCE_WEBUI_CHAT_PRESENTATION,
    resolve_websocket_resource_action,
    resolve_websocket_resource_event_types,
)
from features.api.runtime.event_enqueue import enqueue_event_or_warn

__all__ = ("apply_websocket_resource_interests",)


LOGGER_NAME = "SoAI.features.api.websocket_resource_interests"
OPERATION_APPLY_RESOURCE_INTERESTS = "api_system.websocket.resource_interests.apply"


async def apply_websocket_resource_interests(
    data: JSONDict,
    *,
    runtime_context: WebsocketEventRuntimeContext,
) -> None:
    generation_value = data.get("generation")
    resources_value = data.get("resources")
    normalized_resources = _normalize_requested_resources(resources_value)
    selector_valid, requested_selector = normalize_chat_presentation_selector(
        data.get("chat_presentation_conversation_id"),
        presentation_requested=(
            normalized_resources is not None
            and RESOURCE_WEBUI_CHAT_PRESENTATION in normalized_resources
        ),
        selector_present="chat_presentation_conversation_id" in data,
    )
    if not is_strict_int(generation_value):
        await _enqueue_resource_interest_error(
            runtime_context,
            "Invalid resource interest payload.",
            reason="malformed",
            resources=normalized_resources,
        )
        return

    generation = generation_value
    if generation < 0 or normalized_resources is None or not selector_valid:
        await _enqueue_resource_interest_error(
            runtime_context,
            "Invalid resource interest payload.",
            reason="malformed",
            generation=(generation if generation >= 0 else None),
            resources=normalized_resources,
        )
        return

    connection = runtime_context.connection
    requested_resources = normalized_resources
    if generation < connection.resource_interest_generation:
        await _enqueue_resource_interest_error(
            runtime_context,
            "Resource interest generation is stale.",
            reason="stale_generation",
            generation=generation,
            resources=requested_resources,
        )
        return
    if generation == connection.resource_interest_generation:
        if (
            requested_resources != connection.resource_interests
            or requested_selector != connection.chat_presentation_conversation_id
        ):
            await _enqueue_resource_interest_error(
                runtime_context,
                "Resource interest generation conflicts with the accepted resources.",
                reason="generation_conflict",
                generation=generation,
                resources=requested_resources,
            )
            return
        _enqueue_resource_interest_acknowledgement(
            runtime_context,
            generation,
            requested_resources,
            requested_selector,
        )
        return
    requested_event_types = await _resolve_requested_event_types(
        requested_resources,
        generation=generation,
        runtime_context=runtime_context,
    )
    if requested_event_types is None:
        return
    if requested_selector is not None and not await chat_presentation_conversation_is_visible(
        requested_selector,
        runtime_context=runtime_context,
    ):
        await _enqueue_resource_interest_error(
            runtime_context,
            "Unknown or unauthorized chat presentation conversation.",
            reason="unknown_conversation",
            generation=generation,
            resources=requested_resources,
        )
        return

    event_handler = connection.event_handler
    if event_handler is None:
        raise StateError("Websocket event handler is unavailable.")

    event_bus = runtime_context.api_context.dependencies.event_bus
    current_event_types = set(connection.resource_interest_event_types)
    removed_event_types = current_event_types - requested_event_types
    added_event_types = requested_event_types - current_event_types
    _apply_event_type_changes_atomically(
        event_bus=event_bus,
        event_handler=event_handler,
        removed_event_types=removed_event_types,
        added_event_types=added_event_types,
    )

    connection.resource_interests = requested_resources
    connection.resource_interest_event_types = requested_event_types
    connection.chat_presentation_conversation_id = requested_selector
    connection.subscribed_types.difference_update(removed_event_types)
    connection.subscribed_types.update(added_event_types)
    connection.resource_interest_generation = generation
    _enqueue_resource_interest_acknowledgement(
        runtime_context,
        generation,
        requested_resources,
        requested_selector,
    )


def _normalize_requested_resources(resources: JSONValue | None) -> set[str] | None:
    if not is_str_list(resources):
        return None
    normalized = [resource.strip() for resource in resources]
    if any(not resource for resource in normalized) or len(set(normalized)) != len(normalized):
        return None
    return set(normalized)


async def _resolve_requested_event_types(
    resources: set[str],
    *,
    generation: int,
    runtime_context: WebsocketEventRuntimeContext,
) -> set[type[Event]] | None:
    event_types: set[type[Event]] = set()
    for resource in resources:
        resource_event_types = resolve_websocket_resource_event_types(resource)
        if resource_event_types is None:
            await _enqueue_resource_interest_error(
                runtime_context,
                f"Unknown live resource interest: {resource}",
                reason="unknown_resource",
                generation=generation,
                resources=resources,
            )
            return None
        required_action = resolve_websocket_resource_action(resource)
        if (
            required_action is None
            or required_action not in runtime_context.connection.granted_actions
        ):
            await _enqueue_resource_interest_error(
                runtime_context,
                f"Unauthorized live resource interest: {resource}",
                reason="forbidden",
                generation=generation,
                resources=resources,
            )
            return None
        event_types.update(resource_event_types)
    return event_types


async def _enqueue_resource_interest_error(
    runtime_context: WebsocketEventRuntimeContext,
    message: str,
    *,
    reason: str,
    generation: int | None = None,
    resources: set[str] | None = None,
) -> None:
    details: JSONDict = {"reason": reason}
    if generation is not None:
        details["generation"] = generation
    if resources is not None:
        details["resources"] = sorted(resources)
    await enqueue_websocket_error(
        runtime_context.enqueue_warning_tracker,
        runtime_context.connection.queue,
        runtime_context.trace_id,
        WebSocketEventTypes.INVALID_RESOURCE_INTEREST,
        message,
        code="invalid_request_error",
        details=details,
    )


def _enqueue_resource_interest_acknowledgement(
    runtime_context: WebsocketEventRuntimeContext,
    generation: int,
    resources: set[str],
    chat_presentation_conversation_id: str | None,
) -> None:
    enqueue_event_or_warn(
        runtime_context.enqueue_warning_tracker,
        runtime_context.connection.queue,
        build_websocket_event_payload(
            WebSocketEventTypes.RESOURCE_INTERESTS_APPLIED,
            {
                "generation": generation,
                "resources": sorted(resources),
                "chat_presentation_conversation_id": chat_presentation_conversation_id,
            },
        ),
        "WebSocket resource interests acknowledgement",
    )


def _apply_event_type_changes_atomically(
    *,
    event_bus: EventBusProtocol,
    event_handler: Callable[[Event], Awaitable[None]],
    removed_event_types: set[type[Event]],
    added_event_types: set[type[Event]],
) -> None:
    subscribed: list[type[Event]] = []
    unsubscribed: list[type[Event]] = []
    try:
        for event_type in added_event_types:
            event_bus.subscribe(event_type, event_handler)
            subscribed.append(event_type)
        for event_type in removed_event_types:
            event_bus.unsubscribe(event_type, event_handler)
            unsubscribed.append(event_type)
    except Exception as exception:
        coerced_exception = coerce_to_soai_error(
            exception,
            operation=OPERATION_APPLY_RESOURCE_INTERESTS,
        )
        log_exception(
            get_logger(LOGGER_NAME),
            coerced_exception,
            message="WebSocket resource interest subscription update failed.",
            operation=OPERATION_APPLY_RESOURCE_INTERESTS,
            level="error",
        )
        for event_type in reversed(unsubscribed):
            event_bus.subscribe(event_type, event_handler)
        for event_type in reversed(subscribed):
            event_bus.unsubscribe(event_type, event_handler)
        raise
