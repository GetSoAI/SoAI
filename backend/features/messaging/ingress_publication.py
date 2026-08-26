"""SoAI - Messaging admission event publication [backend/features/messaging/ingress_publication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.conversation_publication import (
    publish_conversation_created,
    publish_conversation_updated,
)
from core.logging.trace import get_logger
from features.api.routes.webui.conversation_input_queue_events import (
    publish_current_input_queue_changed,
)
from features.chat.conversation_input_cancellation import (
    cancel_active_conversation_input,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("publish_messaging_admission",)

LOGGER_NAME = "SoAI.features.messaging.ingress_publication"
OPERATION = "messaging.ingress.publish"


async def publish_messaging_admission(
    api_dependencies: ApiDependencies,
    result: JSONDict,
) -> None:
    status = result.get("status")
    if status not in {
        "accepted",
        "cancel_pending",
        "reset_pending",
        "reset_waiting",
        "reset_completed",
    }:
        return
    user_id = result.get("user_id")
    conv_id = result.get("conv_id")
    if not isinstance(user_id, int) or not isinstance(conv_id, str):
        return
    try:
        cancellation_input_id = result.get("cancellation_input_id")
        if isinstance(cancellation_input_id, str):
            await cancel_active_conversation_input(
                api_dependencies,
                user_id=user_id,
                conv_id=str(result.get("old_conv_id") or conv_id),
                input_id=cancellation_input_id,
                reason="Messaging control requested conversation input cancellation.",
            )
        if status in {"cancel_pending", "reset_pending", "reset_waiting"}:
            await publish_current_input_queue_changed(
                api_dependencies=api_dependencies,
                user_id=user_id,
                conv_id=conv_id,
            )
            return
        if status == "reset_completed":
            old_conv_id = result.get("old_conv_id")
            old_revision = result.get("old_last_modified_at_ms")
            if isinstance(old_conv_id, str) and isinstance(old_revision, int):
                await publish_conversation_updated(
                    api_dependencies.event_bus,
                    user_id=user_id,
                    conv_id=old_conv_id,
                    last_modified_at_ms=old_revision,
                    settings_authority_changed=True,
                )
        conversation = await api_dependencies.database_conversations.get_conversation(
            conv_id,
            user_id,
        )
        if conversation is not None:
            if result.get("conversation_created") is True:
                await publish_conversation_created(
                    api_dependencies.event_bus,
                    user_id=user_id,
                    conversation_record=conversation,
                )
            else:
                revision = conversation.get("last_modified_at_ms")
                if isinstance(revision, int):
                    await publish_conversation_updated(
                        api_dependencies.event_bus,
                        user_id=user_id,
                        conv_id=conv_id,
                        last_modified_at_ms=revision,
                        is_archived=False,
                    )
        await publish_current_input_queue_changed(
            api_dependencies=api_dependencies,
            user_id=user_id,
            conv_id=conv_id,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            coerce_to_soai_error(exception, operation=OPERATION),
            message="Messaging admission publication failed after durable acceptance.",
            operation=OPERATION,
            level="warning",
            details={"user_id": user_id, "conv_id": conv_id},
        )
