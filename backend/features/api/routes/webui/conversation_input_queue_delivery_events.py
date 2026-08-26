"""SoAI - Input queue delivery knowledge event publication [backend/features/api/routes/webui/conversation_input_queue_delivery_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.types.json import is_json_dict, is_json_list
from features.api.routes.webui.conversation_attachments.events import (
    publish_unique_knowledge_attachment_summaries,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("publish_knowledge_events_from_delivery_result",)

LOGGER_NAME = "SoAI.features.api.conversation_input_queue_delivery_events"
OPERATION_INPUT_QUEUE_DELIVERY_KNOWLEDGE_EVENTS = "webui.input_queue.delivery.knowledge_events"


async def publish_knowledge_events_from_delivery_result(
    api_dependencies: ApiDependencies,
    result: JSONDict | None,
) -> None:
    if result is None:
        return
    raw_summaries = result.pop("knowledge_attachment_summaries", None)
    if raw_summaries is None:
        return
    if not is_json_list(raw_summaries):
        raise StateError("Conversation input delivery knowledge summaries are invalid.")
    summaries: list[JSONDict] = []
    for summary in raw_summaries:
        if not is_json_dict(summary):
            raise StateError("Conversation input delivery knowledge summary is invalid.")
        summaries.append(summary)
    try:
        await publish_unique_knowledge_attachment_summaries(
            api_dependencies.event_bus,
            summaries=summaries,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_INPUT_QUEUE_DELIVERY_KNOWLEDGE_EVENTS,
        )
        log_handled_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Failed to publish conversation input delivery knowledge events.",
            operation=OPERATION_INPUT_QUEUE_DELIVERY_KNOWLEDGE_EVENTS,
            level="debug",
        )
