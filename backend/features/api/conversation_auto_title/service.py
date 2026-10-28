"""SoAI - Conversation auto-title generation service [backend/features/api/conversation_auto_title/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.deadlines import MonotonicDeadline, deadline_after
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.conversation_publication import publish_conversation_title_updated
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
    is_automatic_title_committed,
    load_auto_title_attempt_state,
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
_REASON_DEADLINE_EXPIRED = "deadline_expired"


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
    background_deadline = deadline_after(_AUTO_TITLE_BACKGROUND_TIMEOUT_SECONDS)
    background_scope = asyncio.timeout_at(background_deadline.deadline_monotonic)
    try:
        async with background_scope:
            generated_title = await _generate_admitted_title(
                api_dependencies=api_dependencies,
                runtime=runtime,
                attempt_state=attempt_state,
                logger=logger,
            )
            if background_scope.expired() or background_deadline.remaining_seconds() <= 0:
                _log_auto_title_skip(logger, runtime=runtime, reason=_REASON_DEADLINE_EXPIRED)
                return
            if generated_title is not None:
                await uncancel_then_cleanup(
                    _persist_and_publish_title(
                        api_dependencies=api_dependencies,
                        runtime=runtime,
                        attempt_state=attempt_state,
                        generated_title=generated_title,
                        background_deadline=background_deadline,
                        logger=logger,
                    )
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


async def _generate_admitted_title(
    *,
    api_dependencies: ApiDependencies,
    runtime: AssistantTimelineRuntime,
    attempt_state: AutoTitleAttemptState,
    logger: TraceLogger,
) -> str | None:
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
        return None
    if not await orchestrator_is_idle(api_dependencies):
        _log_auto_title_skip(logger, runtime=runtime, reason=REASON_ORCHESTRATOR_BACKLOG)
        return None
    async with acquire_auto_title_slot(api_dependencies, conversation_id=runtime.conv_id):
        generated_title = await generate_auto_title(
            api_dependencies=api_dependencies,
            runtime=runtime,
            user_message=attempt_state.first_user_message,
            assistant_message=attempt_state.first_assistant_message,
        )
    if generated_title is None:
        _log_auto_title_skip(logger, runtime=runtime, reason=_REASON_PARSE_FAILED)
        return None
    if generated_title == attempt_state.default_title:
        _log_auto_title_skip(logger, runtime=runtime, reason=_REASON_DEFAULT_TITLE)
        return None
    return generated_title


async def _persist_and_publish_title(
    *,
    api_dependencies: ApiDependencies,
    runtime: AssistantTimelineRuntime,
    attempt_state: AutoTitleAttemptState,
    generated_title: str,
    background_deadline: MonotonicDeadline,
    logger: TraceLogger,
) -> None:
    if background_deadline.remaining_seconds() <= 0:
        _log_auto_title_skip(logger, runtime=runtime, reason=_REASON_DEADLINE_EXPIRED)
        return
    conversations = api_dependencies.database_conversations
    try:
        updated_record = await conversations.update_conversation_title_if_matches(
            runtime.conv_id,
            runtime.user_id,
            attempt_state.default_title,
            generated_title,
            require_title_auto_update_allowed=True,
        )
    except RECOVERABLE_EXCEPTIONS:
        updated_record = await conversations.get_conversation(runtime.conv_id, runtime.user_id)
        if not is_automatic_title_committed(updated_record, generated_title):
            raise
    if updated_record is None:
        _log_auto_title_skip(logger, runtime=runtime, reason=_REASON_CAS_MISS)
        return
    await publish_conversation_title_updated(
        api_dependencies.event_bus,
        user_id=runtime.user_id,
        conv_id=runtime.conv_id,
        conversation_record=updated_record,
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
