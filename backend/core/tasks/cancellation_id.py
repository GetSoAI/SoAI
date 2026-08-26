"""SoAI - Cancellation ID extraction and validation [backend/core/tasks/cancellation_id.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable

from core.concurrency.context import get_context_cancellation_id
from core.errors.exceptions import ValidationError
from core.tasks.protocols import CommandWithContextProtocol

__all__ = (
    "ensure_command_cancellation_id",
    "get_command_cancellation_id",
    "require_command_cancellation_id",
)


def get_command_cancellation_id(command: CommandWithContextProtocol) -> str | None:
    try:
        context = command.context
    except AttributeError:
        context = None
    cancellation_id = get_context_cancellation_id(context)
    return str(cancellation_id) if cancellation_id is not None else None


def require_command_cancellation_id(command: CommandWithContextProtocol) -> str:
    cancellation_id = get_command_cancellation_id(command)
    if not cancellation_id:
        raise ValidationError(
            "Command requires an associated request context with a cancellation_id for cancellation.",
        )
    return cancellation_id


def ensure_command_cancellation_id(
    command: CommandWithContextProtocol,
    *,
    default_factory: Callable[[], str],
) -> str:
    cancellation_id = get_command_cancellation_id(command)
    if cancellation_id:
        return cancellation_id
    generated = default_factory()
    normalized = str(generated or "").strip()
    if not normalized:
        raise ValidationError("default_factory returned an empty cancellation_id.")
    return normalized
