"""SoAI - Shared inference terminal handler builders [backend/core/events/inference_terminal_handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.events.non_streaming_hard_deadline import TerminalEventHandler
from core.events.types_models_streaming import InferenceResultEvent
from core.events.types_plugins import ErrorEvent
from core.events.types_tasks import TaskCompleteEvent

__all__ = ("build_inference_terminal_handlers",)


def build_inference_terminal_handlers[EventType, Result](
    *,
    handle_inference_result: Callable[[EventType], Awaitable[Result]],
    handle_error: Callable[[EventType], Awaitable[Result]],
    handle_complete: Callable[[EventType], Awaitable[Result]],
) -> tuple[
    TerminalEventHandler[EventType, Result],
    TerminalEventHandler[EventType, Result],
    TerminalEventHandler[EventType, Result],
]:
    return (
        TerminalEventHandler(
            matches=lambda event: isinstance(event, InferenceResultEvent),
            handler=handle_inference_result,
        ),
        TerminalEventHandler(
            matches=lambda event: isinstance(event, ErrorEvent),
            handler=handle_error,
        ),
        TerminalEventHandler(
            matches=lambda event: isinstance(event, TaskCompleteEvent),
            handler=handle_complete,
        ),
    )
