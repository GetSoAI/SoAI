"""SoAI - Input queue route event publishing [backend/features/api/routes/webui/conversation_input_queue_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_system import ConversationInputsChangedEvent
from core.logging.trace import get_logger
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "publish_current_input_queue_changed",
    "publish_input_queue_changed",
)

LOGGER_NAME = "SoAI.features.api.conversation_input_queue_events"
OPERATION_INPUT_QUEUE_PUBLISH = "webui.input_queue.publish_changed"


async def publish_current_input_queue_changed(
    *,
    api_dependencies: ApiDependencies,
    user_id: int,
    conv_id: str,
) -> None:
    try:
        active = await api_dependencies.database_input_queue.list_active_inputs(
            conv_id=conv_id,
            user_id=user_id,
        )
        await publish_input_queue_changed(
            api_dependencies=api_dependencies,
            user_id=user_id,
            conv_id=conv_id,
            active_count=len(active),
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_INPUT_QUEUE_PUBLISH,
        )
        log_handled_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Failed to resolve current input queue event (non-critical).",
            operation=OPERATION_INPUT_QUEUE_PUBLISH,
            level="debug",
            details={"user_id": int(user_id), "conv_id": conv_id},
        )


async def publish_input_queue_changed(
    *,
    api_dependencies: ApiDependencies,
    user_id: int,
    conv_id: str,
    active_count: int,
) -> None:
    try:
        await api_dependencies.event_bus.publish(
            ConversationInputsChangedEvent(
                user_id=user_id,
                conv_id=conv_id,
                active_count=int(active_count),
                last_modified_at_ms=epoch_ms(),
            ),
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_INPUT_QUEUE_PUBLISH,
        )
        log_handled_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Failed to publish input queue changed event (non-critical).",
            operation=OPERATION_INPUT_QUEUE_PUBLISH,
            level="debug",
            details={
                "user_id": int(user_id),
                "conv_id": conv_id,
                "active_count": int(active_count),
            },
        )
