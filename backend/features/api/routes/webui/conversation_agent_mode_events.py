"""SoAI - Conversation agent mode changed event publishing [backend/features/api/routes/webui/conversation_agent_mode_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from features.agent.events.types import AgentModeChangedEvent

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from features.api.runtime.context import ApiContext

__all__ = ("publish_agent_mode_changed_event",)

OPERATION = "webui.agent_mode.publish_mode_changed"


async def publish_agent_mode_changed_event(
    api_context: ApiContext,
    *,
    user_id: int,
    conv_id: str,
    mode: str,
    logger: LoggerProtocol | None = None,
) -> None:
    try:
        sequence = await api_context.dependencies.agent_chronology_sequencer.next_sequence(
            conv_id=conv_id,
            user_id=user_id,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        if logger is not None:
            log_handled_exception(
                logger,
                coerce_to_soai_error(
                    exception,
                    operation="webui.agent_mode.publish_mode_changed",
                ),
                message="Failed to allocate sequence for mode change event (non-critical).",
                operation=OPERATION,
                level="debug",
            )
        return
    try:
        await api_context.dependencies.event_bus.publish(
            AgentModeChangedEvent(
                user_id=user_id,
                conv_id=conv_id,
                turn_id="",
                iteration_index=0,
                sequence=sequence,
                mode=mode,
            ),
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        if logger is not None:
            log_handled_exception(
                logger,
                coerce_to_soai_error(
                    exception,
                    operation="webui.agent_mode.publish_mode_changed",
                ),
                message="Failed to publish agent mode change event (non-critical).",
                operation=OPERATION,
                level="debug",
            )
