"""SoAI - Model output contract error classification [backend/core/openai/model_output_contract_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.errors.error_types import ErrorType
from core.types.json import JSONValue

__all__ = (
    "INVALID_TOOL_CALL_JSON_FAILURE_TYPE",
    "MODEL_OUTPUT_CONTRACT_ERROR_CODE",
    "build_invalid_tool_call_json_error_details",
    "is_invalid_tool_call_json_contract_error",
)

MODEL_OUTPUT_CONTRACT_ERROR_CODE = ErrorType.MODEL_OUTPUT_CONTRACT.value
INVALID_TOOL_CALL_JSON_FAILURE_TYPE = "invalid_tool_call_json"
_DETAIL_MAX_CHARS = 4096
_INVALID_TOOL_CALL_JSON_MARKERS: tuple[str, ...] = (
    "invalid tool-call json",
    "invalid tool call json",
    "error parsing tool call",
)
_TOOL_JSON_DETAIL_MARKERS: tuple[str, ...] = (
    "value looks like object",
    "can't find closing",
)
_TOOL_JSON_INVALID_CHARACTER_CONTEXT_MARKERS: tuple[str, ...] = (
    "argument",
    "arguments",
    "json",
    "tool call",
    "tool-call",
)
_TOOL_XML_DETAIL_MARKERS: tuple[str, ...] = (
    "<function>",
    "</parameter>",
    "<tool_call",
    "tool-call xml",
)


def is_invalid_tool_call_json_contract_error(
    *,
    message: str | None,
    error_type: str | None = None,
    tool_call_context: bool = False,
) -> bool:
    del error_type
    normalized_message = str(message or "").strip().lower()
    if not normalized_message:
        return False
    if any(marker in normalized_message for marker in _INVALID_TOOL_CALL_JSON_MARKERS):
        return True
    if "xml syntax error" in normalized_message:
        return tool_call_context or any(
            marker in normalized_message for marker in _TOOL_XML_DETAIL_MARKERS
        )
    if "tool" not in normalized_message:
        return False
    if any(marker in normalized_message for marker in _TOOL_JSON_DETAIL_MARKERS):
        return True
    if "invalid character" not in normalized_message:
        return False
    return any(
        marker in normalized_message for marker in _TOOL_JSON_INVALID_CHARACTER_CONTEXT_MARKERS
    )


def build_invalid_tool_call_json_error_details(
    *,
    provider: str,
    source_model_id: str,
    provider_detail: str,
    extra: Mapping[str, JSONValue] | None = None,
) -> dict[str, JSONValue]:
    detail = str(provider_detail or "").strip()
    details: dict[str, JSONValue] = dict(extra) if extra else {}
    details["provider"] = str(provider or "").strip()
    details["failure_type"] = INVALID_TOOL_CALL_JSON_FAILURE_TYPE
    details["source_model_id"] = str(source_model_id or "").strip()
    details["provider_detail"] = detail[:_DETAIL_MAX_CHARS]
    return details
