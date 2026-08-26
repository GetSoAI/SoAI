"""SoAI - Conversation auto-title generation service [backend/features/api/conversation_auto_title/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.conversation_publication import publish_conversation_updated
from core.logging.protocols import TraceLogger
from core.logging.trace import get_logger
from core.validation.strings import coerce_optional_trimmed_str
from features.api.conversation_auto_title.admission import (
    REASON_ORCHESTRATOR_BACKLOG,
    REASON_ORIGINATING_TASK_UNSETTLED,
    await_auto_title_admission,
    orchestrator_is_idle,
)
from features.api.conversation_auto_title.attempt_state import (
    AutoTitleAttemptState,
    load_auto_title_attempt_state,
    require_last_modified_at_ms,
)
from features.api.conversation_auto_title.inference import (
    acquire_auto_title_slot,
    generate_auto_title,
)
from features.assistant_timeline.models import AssistantTimelineRuntime

if TYPE_CHECKING:
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "generate_and_persist_auto_title",
    "spawn_auto_title_generation_if_needed",
)

LOGGER_NAME = "SoAI.features.api.service"
SPAWN_OPERATION = "conversation_auto_title.spawn_if_needed"
GENERATE_OPERATION = "conversation_auto_title.generate_and_persist"
_FIRST_ASSISTANT_REPLY_MESSAGE_INDEX = 1
_AUTO_TITLE_BACKGROUND_TIMEOUT_SECONDS = 23.0
_REASON_MISSING_MODEL = "missing_model"
_REASON_MISSING_ORIGINATING_TASK = "missing_originating_task"
_REASON_PARSE_FAILED = "generation_failed"
_REASON_DEFAULT_TITLE = "default_title_generated"
_REASON_CAS_MISS = "compare_and_swap_miss"


async def spawn_auto_title_generation_if_needed(
    *,
    api_dependencies: ApiDependencies,
    runtime: AssistantTimelineRuntime,
    completion_succeeded: bool,
) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        if (
            not completion_succeeded
            or runtime.message_index != _FIRST_ASSISTANT_REPLY_MESSAGE_INDEX
        ):
            return
        if runtime.model_variant_index not in (None, 0):
            return
        if coerce_optional_trimmed_str(runtime.model_id) is None:
            _log_auto_title_skip(logger, runtime=runtime, reason=_REASON_MISSING_MODEL)
            return
        if runtime.active_task_id is None or not runtime.active_task_id.strip():
            _log_auto_title_skip(logger, runtime=runtime, reason=_REASON_MISSING_ORIGINATING_TASK)
            return
        attempt_state = await load_auto_title_attempt_state(
            api_dependencies=api_dependencies,
            conv_id=runtime.conv_id,
            user_id=runtime.user_id,
        )
        if attempt_state is None:
            return
        await generate_and_persist_auto_title(
            api_dependencies=api_dependencies,
            runtime=runtime,
            attempt_state=attempt_state,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=SPAWN_OPERATION,
        )
        log_handled_exception(
            logger,
            coerced,
            message="Conversation auto-title spawn failed (non-critical).",
            operation=SPAWN_OPERATION,
            details={"conv_id": runtime.conv_id, "user_id": runtime.user_id},
            level="debug",
        )


async def generate_and_persist_auto_title(
    *,
    api_dependencies: ApiDependencies,
    runtime: AssistantTimelineRuntime,
    attempt_state: AutoTitleAttemptState,
) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        generated_title: str | None = None
        async with asyncio.timeout(_AUTO_TITLE_BACKGROUND_TIMEOUT_SECONDS):
            admission_result = await await_auto_title_admission(
                api_dependencies=api_dependencies,
                originating_task_id=runtime.active_task_id or "",
            )
            if not admission_result.admitted:
                _log_auto_title_skip(
                    logger,
                    runtime=runtime,
                    reason=admission_result.reason or REASON_ORIGINATING_TASK_UNSETTLED,
                )
                return
            if not await orchestrator_is_idle(api_dependencies):
                _log_auto_title_skip(
                    logger,
                    runtime=runtime,
                    reason=REASON_ORCHESTRATOR_BACKLOG,
                )
                return
            async with acquire_auto_title_slot(
                api_dependencies,
                conversation_id=runtime.conv_id,
            ):
                generated_title = await generate_auto_title(
                    api_dependencies=api_dependencies,
                    runtime=runtime,
                    user_message=attempt_state.first_user_message,
                    assistant_message=attempt_state.first_assistant_message,
                )
            if generated_title is None:
                _log_auto_title_skip(logger, runtime=runtime, reason=_REASON_PARSE_FAILED)
                return
            if generated_title == attempt_state.default_title:
                _log_auto_title_skip(logger, runtime=runtime, reason=_REASON_DEFAULT_TITLE)
                return
            updated_record = (
                await api_dependencies.database_conversations.update_conversation_title_if_matches(
                    runtime.conv_id,
                    runtime.user_id,
                    attempt_state.default_title,
                    generated_title,
                )
            )
            if updated_record is None:
                _log_auto_title_skip(logger, runtime=runtime, reason=_REASON_CAS_MISS)
                return
            last_modified_at_ms = require_last_modified_at_ms(updated_record)
            await publish_conversation_updated(
                api_dependencies.event_bus,
                user_id=runtime.user_id,
                conv_id=runtime.conv_id,
                last_modified_at_ms=last_modified_at_ms,
                title=generated_title,
            )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=GENERATE_OPERATION,
        )
        log_handled_exception(
            logger,
            coerced,
            message="Conversation auto-title generation failed (non-critical).",
            operation=GENERATE_OPERATION,
            details={"conv_id": runtime.conv_id, "user_id": runtime.user_id},
            level="debug",
        )


def _log_auto_title_skip(
    logger: TraceLogger,
    *,
    runtime: AssistantTimelineRuntime,
    reason: str,
) -> None:
    if not reason:
        return
    logger.debug(
        "Conversation auto-title skipped: reason=%s conv_id=%s user_id=%s",
        reason,
        runtime.conv_id,
        runtime.user_id,
    )
