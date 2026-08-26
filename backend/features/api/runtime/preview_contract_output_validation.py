"""SoAI - Semantic validation for strict WebUI preview-contract output [backend/features/api/runtime/preview_contract_output_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.formatting.markdown_code_segments import (
    split_fenced_segments,
    split_inline_code_segments,
)
from core.preview_contract.preview_contract import analyze_preview_contract_syntax
from features.api.runtime.preview_contract_reference_validation import (
    validate_absolute_path_reference,
    validate_remote_url_reference,
    validate_virtual_path_reference,
)
from features.api.runtime.preview_contract_repair import attempt_preview_contract_repair
from features.api.runtime.preview_contract_scope import (
    ConversationPreviewScope,
    load_conversation_preview_scope,
)

if TYPE_CHECKING:
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "PreviewContractOutputValidationResult",
    "validate_preview_contract_output",
)

_PREVIEW_REFERENCE_MARKER = "[[preview:"


@dataclass(frozen=True, slots=True)
class PreviewContractOutputValidationResult:
    compliant: bool
    resolved_text: str
    retry_detail: str | None
    reason_code: str | None
    repair_attempted: bool
    repair_succeeded: bool


async def validate_preview_contract_output(
    api_dependencies: ApiDependencies,
    *,
    conv_id: str,
    user_id: int,
    assistant_text: str,
) -> PreviewContractOutputValidationResult:
    normalized_text = str(assistant_text or "")
    original_failure = await _validate_preview_contract_text(
        api_dependencies,
        conv_id=conv_id,
        user_id=user_id,
        assistant_text=normalized_text,
    )
    if original_failure is None:
        return PreviewContractOutputValidationResult(
            compliant=True,
            resolved_text=normalized_text,
            retry_detail=None,
            reason_code=None,
            repair_attempted=False,
            repair_succeeded=False,
        )
    repair_result = attempt_preview_contract_repair(normalized_text)
    if repair_result.changed:
        repaired_failure = await _validate_preview_contract_text(
            api_dependencies,
            conv_id=conv_id,
            user_id=user_id,
            assistant_text=repair_result.text,
        )
        if repaired_failure is None:
            return PreviewContractOutputValidationResult(
                compliant=True,
                resolved_text=repair_result.text,
                retry_detail=None,
                reason_code=original_failure[0],
                repair_attempted=True,
                repair_succeeded=True,
            )
        return PreviewContractOutputValidationResult(
            compliant=False,
            resolved_text=normalized_text,
            retry_detail=repaired_failure[1],
            reason_code=repaired_failure[0],
            repair_attempted=True,
            repair_succeeded=False,
        )
    return PreviewContractOutputValidationResult(
        compliant=False,
        resolved_text=normalized_text,
        retry_detail=original_failure[1],
        reason_code=original_failure[0],
        repair_attempted=False,
        repair_succeeded=False,
    )


async def _validate_preview_contract_text(
    api_dependencies: ApiDependencies,
    *,
    conv_id: str,
    user_id: int,
    assistant_text: str,
) -> tuple[str, str] | None:
    if _contains_preview_reference_marker_in_protected_segments(assistant_text):
        return (
            "noncanonical_reference_syntax",
            "Do not place preview references inside fenced code blocks, inline code spans, or tool calls.",
        )
    syntax = analyze_preview_contract_syntax(assistant_text)
    if not syntax.compliant:
        if syntax.reason_code == "missing_preview_reference":
            return (
                "missing_preview_reference",
                "Provide at least one canonical preview reference in the assistant response body.",
            )
        return (
            "noncanonical_reference_syntax",
            "Use only canonical [[preview:<type>:<target>]] references in the assistant response body.",
        )
    references = syntax.references
    if not references:
        return (
            "missing_preview_reference",
            "Provide at least one canonical preview reference in the assistant response body.",
        )
    scope: ConversationPreviewScope | None = None
    for reference in references:
        if reference.type == "remote_url":
            failure_detail = validate_remote_url_reference(reference.target)
        else:
            if scope is None:
                scope = await load_conversation_preview_scope(
                    api_dependencies,
                    conv_id=conv_id,
                    user_id=user_id,
                )
                if scope is None:
                    return (
                        "absolute_path_preview_scope_unavailable",
                        "Absolute path preview references are unavailable for this conversation.",
                    )
            if reference.type == "absolute_path":
                failure_detail = await validate_absolute_path_reference(scope, reference.target)
            else:
                failure_detail = await validate_virtual_path_reference(scope, reference.target)
        if failure_detail is not None:
            return failure_detail
    return None


def _contains_preview_reference_marker_in_protected_segments(assistant_text: str) -> bool:
    normalized = str(assistant_text or "")
    if not normalized or _PREVIEW_REFERENCE_MARKER not in normalized:
        return False
    if _contains_preview_reference_marker_in_tool_calls(normalized):
        return True
    for protected_fence, fenced_segment in split_fenced_segments(normalized):
        if protected_fence and _PREVIEW_REFERENCE_MARKER in fenced_segment:
            return True
        if protected_fence:
            continue
        for protected_inline_code, segment in split_inline_code_segments(fenced_segment):
            if protected_inline_code and _PREVIEW_REFERENCE_MARKER in segment:
                return True
    return False


def _contains_preview_reference_marker_in_tool_calls(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    open_tag = "<tool_call"
    close_tag = "</tool_call>"
    start_index = 0
    while True:
        open_index = lowered.find(open_tag, start_index)
        if open_index == -1:
            break
        header_end = lowered.find(">", open_index)
        if header_end == -1:
            break
        header = text[open_index : header_end + 1]
        if _PREVIEW_REFERENCE_MARKER in header:
            return True
        close_index = lowered.find(close_tag, header_end + 1)
        if close_index == -1:
            segment = text[open_index:]
            return _PREVIEW_REFERENCE_MARKER in segment
        segment = text[open_index : close_index + len(close_tag)]
        if _PREVIEW_REFERENCE_MARKER in segment:
            return True
        start_index = close_index + len(close_tag)
    open_tag = "<tool_calls_preview_json>"
    close_tag = "</tool_calls_preview_json>"
    start_index = 0
    while True:
        open_index = lowered.find(open_tag, start_index)
        if open_index == -1:
            break
        close_index = lowered.find(close_tag, open_index + len(open_tag))
        segment = (
            text[open_index : open_index + len(open_tag)]
            if close_index == -1
            else text[open_index : close_index + len(close_tag)]
        )
        if close_index == -1:
            segment = text[open_index:]
            return _PREVIEW_REFERENCE_MARKER in segment
        if _PREVIEW_REFERENCE_MARKER in segment:
            return True
        start_index = close_index + len(close_tag)
    return False
