"""SoAI - Normalization for command execution results [backend/core/state/command_results.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, TypeGuard

from core.errors.error_types import ErrorType
from core.events.types_plugins import ErrorEvent
from core.events.types_tasks import TaskCompleteEvent
from core.serialization.json import normalize_for_json

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "CommandResultView",
    "normalize_command_result",
)


@dataclass(slots=True)
class CommandResultView[T]:
    result_type: Literal["error", "task", "payload", "other"]
    success: bool | None
    payload: JSONValue | None
    error_type: ErrorType | None
    message: str | None
    raw: T


def normalize_command_result[T](result: T) -> CommandResultView[T | dict[Hashable, JSONValue]]:
    if isinstance(result, ErrorEvent):
        return CommandResultView(
            result_type="error",
            success=False,
            payload=None,
            error_type=result.error_type,
            message=result.message,
            raw=result,
        )
    if isinstance(result, TaskCompleteEvent):
        payload = {"message": result.message} if result.success and result.message else None
        return CommandResultView(
            result_type="task",
            success=result.success,
            payload=payload,
            error_type=None,
            message=result.message,
            raw=result,
        )
    if _is_result_dict_candidate(result):
        return CommandResultView(
            result_type="payload",
            success=True,
            payload=normalize_for_json(result),
            error_type=None,
            message=None,
            raw=result,
        )
    normalized_payload: JSONValue = normalize_for_json(result)
    return CommandResultView(
        result_type="other",
        success=True,
        payload={"result": normalized_payload},
        error_type=None,
        message=None,
        raw=result,
    )


def _is_result_dict_candidate[T](
    value: T,
    _value_type: type[T] | None = None,
) -> TypeGuard[dict[Hashable, JSONValue]]:
    _ = _value_type
    return isinstance(value, dict)
