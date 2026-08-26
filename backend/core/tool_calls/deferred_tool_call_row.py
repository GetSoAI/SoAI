"""SoAI - Deferred tool call row normalization [backend/core/tool_calls/deferred_tool_call_row.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.serialization.json import serialize_json_compact_stable
from core.tool_calls.tool_call_location import ToolCallLocation
from core.validation.integers import is_strict_int
from core.validation.strict_numbers import (
    coerce_optional_non_negative_int_strict,
    coerce_optional_positive_int_strict,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "DeferredToolCallIdentity",
    "DeferredToolCallRow",
    "create_deferred_tool_call_identity",
    "load_deferred_tool_call_row_noncritical",
    "normalize_deferred_tool_call_row",
    "serialize_json_record",
)

OPERATION_DEFERRED_TOOL_CALL_ROW_LOAD = "core.tool_calls.deferred_tool_call_row.load"


def serialize_json_record(payload: JSONValue) -> str:
    if not isinstance(payload, dict) or not payload:
        return "{}"
    return serialize_json_compact_stable(payload)


@dataclass(frozen=True, slots=True)
class DeferredToolCallIdentity:
    conv_id: str
    call_id: str
    turn_id: str
    iteration_index: int
    assistant_turn_at_ms: int
    model_variant_index: int


def create_deferred_tool_call_identity(
    *,
    conv_id: str,
    call_id: str,
    turn_id: str,
    iteration_index: int,
    assistant_turn_at_ms: int,
    model_variant_index: int,
) -> DeferredToolCallIdentity:
    return DeferredToolCallIdentity(
        conv_id=conv_id,
        call_id=call_id,
        turn_id=turn_id,
        iteration_index=iteration_index,
        assistant_turn_at_ms=assistant_turn_at_ms,
        model_variant_index=model_variant_index,
    )


@dataclass(frozen=True, slots=True)
class DeferredToolCallRow(ToolCallLocation):
    storage_call_id: str
    thinking_duration_before_ms: int | None
    tool_arguments_json: str
    turn_id: str | None
    iteration_index: int | None


def normalize_deferred_tool_call_row(row: JSONDict | None) -> DeferredToolCallRow | None:
    if not isinstance(row, dict):
        return None
    storage_call_id = str(row.get("id") or "").strip()
    conv_id = str(row.get("conv_id") or "").strip()
    message_index_value = row.get("message_index")
    sequence_index_value = row.get("sequence_index")
    assistant_at_ms_value = row.get("assistant_at_ms")
    assistant_turn_at_ms_value = row.get("assistant_turn_at_ms")
    model_variant_index_value = row.get("model_variant_index")
    content_index_before_value = row.get("content_index_before")
    thinking_index_before_value = row.get("thinking_index_before")
    if not storage_call_id or not conv_id:
        return None
    if not is_strict_int(message_index_value):
        return None
    if not is_strict_int(sequence_index_value):
        return None
    if not is_strict_int(assistant_at_ms_value):
        return None
    if not isinstance(assistant_turn_at_ms_value, int) or isinstance(
        assistant_turn_at_ms_value,
        bool,
    ):
        return None
    if not isinstance(model_variant_index_value, int) or isinstance(
        model_variant_index_value,
        bool,
    ):
        return None
    if not isinstance(content_index_before_value, int) or isinstance(
        content_index_before_value,
        bool,
    ):
        return None
    if not isinstance(thinking_index_before_value, int) or isinstance(
        thinking_index_before_value,
        bool,
    ):
        return None
    thinking_duration_before_ms = coerce_optional_non_negative_int_strict(
        row.get("thinking_duration_before_ms"),
    )
    tool_arguments_json = serialize_json_record(row.get("arguments"))
    turn_id_value = str(row.get("turn_id") or "").strip()
    turn_id = turn_id_value or None
    iteration_index = coerce_optional_non_negative_int_strict(row.get("iteration_index"))
    return DeferredToolCallRow(
        storage_call_id=storage_call_id,
        conv_id=conv_id,
        message_index=int(message_index_value),
        assistant_at_ms=int(assistant_at_ms_value),
        assistant_turn_at_ms=int(assistant_turn_at_ms_value),
        model_variant_index=int(model_variant_index_value),
        sequence_index=int(sequence_index_value),
        content_index_before=int(content_index_before_value),
        thinking_index_before=int(thinking_index_before_value),
        thinking_duration_before_ms=thinking_duration_before_ms,
        tool_arguments_json=tool_arguments_json,
        turn_id=turn_id,
        iteration_index=iteration_index,
    )


async def load_deferred_tool_call_row_noncritical(
    *,
    database_tool_calls: DatabaseToolCallsProtocol,
    logger: LoggerProtocol,
    trace_id: str,
    identity: DeferredToolCallIdentity,
) -> DeferredToolCallRow | None:
    conv_id = str(identity.conv_id or "").strip()
    call_id = str(identity.call_id or "").strip()
    turn_id = str(identity.turn_id or "").strip()
    if not conv_id or not call_id or not turn_id:
        return None
    if not is_strict_int(identity.iteration_index):
        return None
    if identity.iteration_index < 0:
        return None
    assistant_turn_at_ms = coerce_optional_positive_int_strict(identity.assistant_turn_at_ms)
    if assistant_turn_at_ms is None:
        return None
    model_variant_index = coerce_optional_non_negative_int_strict(identity.model_variant_index)
    if model_variant_index is None:
        return None
    try:
        raw = await database_tool_calls.get_tool_call_for_agent_lineage(
            conv_id=conv_id,
            call_id=call_id,
            turn_id=turn_id,
            iteration_index=int(identity.iteration_index),
            assistant_turn_at_ms=assistant_turn_at_ms,
            model_variant_index=model_variant_index,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_DEFERRED_TOOL_CALL_ROW_LOAD,
        )
        log_handled_exception(
            logger,
            coerced,
            message="Failed to load deferred tool call row for live streaming (non-critical).",
            trace_id=trace_id,
            operation=OPERATION_DEFERRED_TOOL_CALL_ROW_LOAD,
            level="warning",
            details={
                "conv_id": conv_id,
                "call_id": call_id,
                "turn_id": turn_id,
                "iteration_index": int(identity.iteration_index),
                "assistant_turn_at_ms": assistant_turn_at_ms,
                "model_variant_index": model_variant_index,
            },
        )
        return None
    return normalize_deferred_tool_call_row(raw)
