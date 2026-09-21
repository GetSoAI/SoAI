"""SoAI - WebUI conversation lifecycle admission [backend/features/api/routes/webui/conversation_lifecycle_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exceptions import ConflictError, StateError, ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS

if TYPE_CHECKING:
    from features.api.runtime.context import ApiContext

__all__ = (
    "require_idle_conversation_stream_lifecycle",
    "run_idle_conversation_lifecycle_operation",
    "run_tracked_conversation_admission",
)


async def run_tracked_conversation_admission[ResultT](
    api_context: ApiContext,
    *,
    admission: Coroutine[None, None, ResultT],
    task_name: str,
    cancellation_note: str,
) -> ResultT:
    results: list[ResultT] = []
    rejected: list[ConflictError | ValidationError] = []

    async def capture_admission() -> None:
        try:
            results.append(await admission)
        except (ConflictError, ValidationError) as exception:
            rejected.append(exception)

    admission_task = create_ephemeral_task(capture_admission(), name=task_name)
    api_context.dependencies.application_control.track_background_task(admission_task)
    try:
        await asyncio.shield(admission_task)
    except asyncio.CancelledError as cancellation:
        try:
            await uncancel_then_cleanup(admission_task)
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            cancellation.add_note(f"{cancellation_note}: {exception}")
        raise
    if rejected:
        raise rejected[0]
    if len(results) != 1:
        raise StateError("Conversation admission completed without exactly one result.")
    return results[0]


async def require_idle_conversation_stream_lifecycle(
    api_context: ApiContext,
    *,
    user_id: int,
    conv_id: str,
) -> None:
    snapshot = await api_context.dependencies.chat_stream_registry.snapshot(
        user_id=user_id,
        conv_id=conv_id,
    )
    if (
        (snapshot.runtime is not None and not snapshot.runtime.terminal_persistence_completed)
        or snapshot.reservation is not None
        or snapshot.cancellation_intent is not None
    ):
        raise ConflictError("Conversation operation requires an idle stream lifecycle.")


async def run_idle_conversation_lifecycle_operation[ResultT](
    api_context: ApiContext,
    *,
    user_id: int,
    conv_id: str,
    operation: Callable[[], Awaitable[ResultT]],
) -> ResultT:
    async with api_context.dependencies.chat_stream_registry.lifecycle_lock(
        user_id=user_id,
        conv_id=conv_id,
    ):
        await require_idle_conversation_stream_lifecycle(
            api_context,
            user_id=user_id,
            conv_id=conv_id,
        )
        active_inputs = await api_context.dependencies.database_input_queue.summarize_active_inputs(
            conv_id=conv_id,
            user_id=user_id,
        )
        if active_inputs.has_active_inputs:
            raise ConflictError("Conversation messages cannot change while input work is active.")
        if await api_context.dependencies.database_stream_cancellations.has_pending(
            conv_id=conv_id,
            user_id=user_id,
        ):
            raise ConflictError(
                "Conversation messages cannot change while cancellation is pending."
            )
        running_turn = await api_context.dependencies.database_agent_turns.get_running_root_turn(
            conv_id=conv_id,
            user_id=user_id,
        )
        if running_turn is not None:
            raise ConflictError("Conversation messages cannot change while an agent is running.")
        return await operation()
