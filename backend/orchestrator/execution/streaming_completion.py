"""SoAI - Structured streaming completion payloads [backend/orchestrator/execution/streaming_completion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.numeric import coerce_float_or_none
from core.files.operations import async_remove_if_exists
from core.types.json_value import coerce_json_dict
from orchestrator.execution.temp_cleanup import is_safe_temp_path

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "StreamingCompletion",
    "cleanup_streaming_completion_artifact",
    "coerce_streaming_completion",
)


@dataclass(frozen=True, slots=True)
class StreamingCompletion:
    usage: JSONDict | None = None
    final_result: JSONDict | None = None
    deferred_terminal_chunks: tuple[bytes, ...] = ()
    binary_replay_temp_path: str | None = None
    chunk_delivery_timeout_seconds: float | None = None


def coerce_streaming_completion(
    value: StreamingCompletion | JSONDict | None,
) -> StreamingCompletion:
    if isinstance(value, StreamingCompletion):
        timeout_seconds = coerce_float_or_none(value.chunk_delivery_timeout_seconds)
        return StreamingCompletion(
            usage=coerce_json_dict(value.usage) if value.usage is not None else None,
            final_result=(
                coerce_json_dict(value.final_result) if value.final_result is not None else None
            ),
            deferred_terminal_chunks=tuple(value.deferred_terminal_chunks),
            binary_replay_temp_path=value.binary_replay_temp_path,
            chunk_delivery_timeout_seconds=timeout_seconds,
        )
    if value is None:
        return StreamingCompletion()
    normalized_value = coerce_json_dict(value)
    if normalized_value is None:
        return StreamingCompletion()
    usage_value = coerce_json_dict(normalized_value.get("usage"))
    if "choices" in normalized_value or "data" in normalized_value:
        return StreamingCompletion(
            usage=usage_value,
            final_result=normalized_value,
        )
    return StreamingCompletion(usage=normalized_value)


async def cleanup_streaming_completion_artifact(
    value: StreamingCompletion | JSONDict | None,
    *,
    temp_directory: str | None,
) -> None:
    completion = coerce_streaming_completion(value)
    temp_path = completion.binary_replay_temp_path
    if not isinstance(temp_path, str) or not is_safe_temp_path(temp_path, temp_directory):
        return
    await async_remove_if_exists(temp_path)
