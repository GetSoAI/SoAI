"""SoAI - Request-fenced Chat stream cancellation operation [backend/features/chat/conversation_stream_cancellation_operation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConflictError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC
from features.api.runtime.chat_stream_registry import ChatStreamCancellationIntent
from features.api.runtime.chat_stream_registry_types import execution_owns_runtime
from features.chat.conversation_stream_cancellation import (
    claim_conversation_stream_runtime_cancellation,
)
from features.chat.conversation_stream_cancellation_effects import (
    schedule_cancellation_input_publication,
    schedule_captured_cancellation_cleanup,
    schedule_runtime_cancellation,
)

if TYPE_CHECKING:
    from core.runtime.request_context import RequestContext
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("ChatStreamCancellationAcceptance", "accept_chat_stream_cancellation")

CANCELLATION_REASON = "User requested cancellation via WebUI."
LOGGER_NAME = "SoAI.features.chat.conversation_stream_cancellation_operation"
OPERATION_SCHEDULE_CLEANUP = "chat.stream_cancellation.schedule_cleanup"
OPERATION_SCHEDULE_INPUT_PUBLICATION = "chat.stream_cancellation.schedule_input_publication"
OPERATION_SCHEDULE_RUNTIME = "chat.stream_cancellation.schedule_runtime"


@dataclass(frozen=True, slots=True)
class ChatStreamCancellationAcceptance:
    conversation_id: str
    request_id: str
    status: Literal["cancellation_requested", "already_terminal", "superseded"]
    forced_input_created: bool = False


async def accept_chat_stream_cancellation(
    *,
    api_dependencies: ApiDependencies,
    context: RequestContext,
    user_id: int,
    conv_id: str,
    request_id: str,
    force_pending_steers: bool,
    allow_unregistered_target: bool = False,
    reason: str = CANCELLATION_REASON,
) -> ChatStreamCancellationAcceptance:
    registry = api_dependencies.chat_stream_registry
    async with registry.lifecycle_lock(user_id=user_id, conv_id=conv_id):
        snapshot = await registry.snapshot(user_id=user_id, conv_id=conv_id)
        runtime = snapshot.runtime
        reservation = snapshot.reservation
        pending_intent = snapshot.cancellation_intent
        if pending_intent is not None and pending_intent.request_id != request_id:
            return ChatStreamCancellationAcceptance(conv_id, request_id, "superseded")
        if runtime is not None and not execution_owns_runtime(request_id, runtime):
            return ChatStreamCancellationAcceptance(conv_id, request_id, "superseded")
        if runtime is None and reservation is not None and reservation.request_id != request_id:
            return ChatStreamCancellationAcceptance(conv_id, request_id, "superseded")
        allow_unpersisted_target = (
            runtime is not None or reservation is not None or allow_unregistered_target
        )
        shell_sessions = api_dependencies.mcp_server.snapshot_openai_shell_sessions(
            user_id=user_id,
            conv_id=conv_id,
        )
        automation_run_ids = tuple(
            await api_dependencies.database_automation_runs.list_active_run_ids_for_conversation(
                user_id,
                conv_id=conv_id,
            ),
        )
        try:
            persisted = await asyncio.wait_for(
                api_dependencies.database_stream_cancellations.accept(
                    conv_id=conv_id,
                    user_id=user_id,
                    request_id=request_id,
                    force_pending_steers=force_pending_steers,
                    allow_unpersisted_target=allow_unpersisted_target,
                ),
                timeout=LOCAL_IO_TIMEOUT_SEC,
            )
        except ConflictError:
            return ChatStreamCancellationAcceptance(conv_id, request_id, "superseded")
        status_value = persisted.get("status")
        if status_value == "already_terminal":
            await registry.clear_cancellation_intent_if_same(
                user_id=user_id,
                conv_id=conv_id,
                request_id=request_id,
            )
            return ChatStreamCancellationAcceptance(conv_id, request_id, "already_terminal")
        if persisted.get("terminal_completed") is not True:
            intent = ChatStreamCancellationIntent(
                user_id=user_id,
                conv_id=conv_id,
                request_id=request_id,
                force_pending_steers=bool(
                    persisted.get("force_pending_steers", force_pending_steers)
                ),
                reason=reason,
            )
            await registry.remember_cancellation_intent(intent)
        if persisted.get("forced_input_created") is True:
            try:
                schedule_cancellation_input_publication(
                    api_dependencies,
                    user_id=user_id,
                    conv_id=conv_id,
                    request_id=request_id,
                )
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                log_exception(
                    get_logger(LOGGER_NAME),
                    coerce_to_soai_error(
                        exception,
                        operation=OPERATION_SCHEDULE_INPUT_PUBLICATION,
                    ),
                    message="Chat cancellation input publication scheduling failed after acceptance.",
                    operation=OPERATION_SCHEDULE_INPUT_PUBLICATION,
                    details={"conv_id": conv_id, "request_id": request_id},
                )
        if runtime is not None and execution_owns_runtime(request_id, runtime):
            cancellation_claimed = await claim_conversation_stream_runtime_cancellation(
                runtime,
                reason,
            )
            if cancellation_claimed:
                try:
                    await schedule_runtime_cancellation(
                        api_dependencies=api_dependencies,
                        context=context,
                        runtime=runtime,
                        automation_run_ids=automation_run_ids,
                        shell_sessions=shell_sessions,
                        reason=reason,
                    )
                except HANDLED_RUNTIME_EXCEPTIONS as exception:
                    log_exception(
                        get_logger(LOGGER_NAME),
                        coerce_to_soai_error(
                            exception,
                            operation=OPERATION_SCHEDULE_RUNTIME,
                        ),
                        message="Chat cancellation runtime scheduling failed after acceptance.",
                        operation=OPERATION_SCHEDULE_RUNTIME,
                        details={"conv_id": conv_id, "request_id": request_id},
                    )
        else:
            try:
                await schedule_captured_cancellation_cleanup(
                    api_dependencies=api_dependencies,
                    context=context,
                    user_id=user_id,
                    conv_id=conv_id,
                    request_id=request_id,
                    automation_run_ids=automation_run_ids,
                    shell_sessions=shell_sessions,
                    reason=reason,
                )
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                log_exception(
                    get_logger(LOGGER_NAME),
                    coerce_to_soai_error(
                        exception,
                        operation=OPERATION_SCHEDULE_CLEANUP,
                    ),
                    message="Chat cancellation cleanup scheduling failed after acceptance.",
                    operation=OPERATION_SCHEDULE_CLEANUP,
                    details={"conv_id": conv_id, "request_id": request_id},
                )
        return ChatStreamCancellationAcceptance(
            conv_id,
            request_id,
            "cancellation_requested",
            persisted.get("forced_input_created") is True,
        )
