"""SoAI - Runtime freshness support for assistant stream state routes [backend/features/api/routes/webui/conversation_stream_state_freshness.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.logging.trace import get_logger
from features.api.runtime.context import ApiContext
from features.assistant_timeline.assistant_text import (
    flush_assistant_visible_chronology,
)
from features.assistant_timeline.publish import ensure_chat_stream_publish_lock

__all__ = ("flush_matching_chat_stream_state_runtime",)

LOGGER_NAME = "SoAI.features.api.conversation_stream_state_freshness"
OPERATION_FORCE_FLUSH = "conversation_stream_state_freshness.force_flush"


async def _await_force_flush_future(future: asyncio.Future[bool]) -> None:
    await future


async def flush_matching_chat_stream_state_runtime(
    api_context: ApiContext,
    *,
    user_id: int,
    conv_id: str,
    assistant_turn_at_ms: int,
    model_variant_index: int,
) -> None:
    logger = get_logger(LOGGER_NAME)
    runtime = await api_context.dependencies.chat_stream_registry.get(
        user_id=user_id,
        conv_id=conv_id,
    )
    if runtime is None:
        return
    flush_future: asyncio.Future[bool] | None = None
    owns_flush = False
    publish_lock = ensure_chat_stream_publish_lock(runtime)
    async with publish_lock:
        existing_future = runtime.stream_state_force_flush_future
        if existing_future is not None and not existing_future.done():
            flush_future = existing_future
        else:
            runtime.stream_state_force_flush_future = None
            should_flush = (
                runtime.user_id == user_id
                and runtime.conv_id == conv_id
                and runtime.assistant_turn_at_ms == assistant_turn_at_ms
                and runtime.model_variant_index == model_variant_index
                and (
                    runtime.assistant_delta_buffer_chars > 0
                    or bool(runtime.assistant_event_buffer)
                    or runtime.assistant_visible_chars > runtime.assistant_persisted_chars
                )
            )
            if should_flush:
                flush_future = asyncio.get_running_loop().create_future()
                runtime.stream_state_force_flush_future = flush_future
                owns_flush = True
    if flush_future is None:
        return
    if not owns_flush:
        await _await_force_flush_future(flush_future)
        return
    try:
        await flush_assistant_visible_chronology(
            runtime=runtime,
            database_messages=api_context.dependencies.database_messages,
            event_bus=api_context.dependencies.event_bus,
        )
        did_flush = True
    except asyncio.CancelledError:
        if not flush_future.done():
            flush_future.set_result(False)
        async with publish_lock:
            if runtime.stream_state_force_flush_future is flush_future:
                runtime.stream_state_force_flush_future = None
        raise
    except Exception as exception:
        coerce_to_soai_error(exception)
        log_exception(
            logger,
            exception,
            message="Failed to flush matching chat stream runtime state.",
            operation=OPERATION_FORCE_FLUSH,
        )
        if not flush_future.done():
            flush_future.set_result(False)
        async with publish_lock:
            if runtime.stream_state_force_flush_future is flush_future:
                runtime.stream_state_force_flush_future = None
        raise
    if not flush_future.done():
        flush_future.set_result(did_flush)
    async with publish_lock:
        if runtime.stream_state_force_flush_future is flush_future:
            runtime.stream_state_force_flush_future = None
