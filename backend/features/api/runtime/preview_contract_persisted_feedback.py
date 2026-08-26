"""SoAI - Preview-contract feedback extraction from stored messages [backend/features/api/runtime/preview_contract_persisted_feedback.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.conversations.canonical_assistant_message import (
    resolve_latest_previous_canonical_assistant_message,
)
from core.preview_contract.preview_contract import PREVIEW_CONTRACT_VIOLATION_CODE
from core.preview_contract.preview_contract_reason_codes import (
    is_preview_contract_reason_code,
)
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "PreviewContractFeedback",
    "resolve_latest_persisted_preview_contract_feedback",
)


@dataclass(frozen=True, slots=True)
class PreviewContractFeedback:
    assistant_at_ms: int
    assistant_turn_at_ms: int
    code: str
    reason_code: str | None
    detail: str | None
    repair_attempted: bool
    repair_succeeded: bool


def resolve_latest_persisted_preview_contract_feedback(
    *,
    messages: Iterable[JSONDict],
    before_timestamp_exclusive: int,
) -> PreviewContractFeedback | None:
    latest_previous_assistant = resolve_latest_previous_canonical_assistant_message(
        messages,
        before_timestamp_exclusive=before_timestamp_exclusive,
    )
    if latest_previous_assistant is None:
        return None
    timestamp_value = latest_previous_assistant.get("timestamp")
    assistant_turn_value = latest_previous_assistant.get("assistant_turn_at_ms")
    timeline_value = latest_previous_assistant.get("assistant_event_timeline")
    if not is_strict_int(timestamp_value):
        return None
    if not is_strict_int(assistant_turn_value):
        return None
    if not isinstance(timeline_value, list):
        return None
    for event in reversed(timeline_value):
        if not isinstance(event, dict) or event.get("event_type") != "error":
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        code_value = payload.get("code")
        if not isinstance(code_value, str) or code_value.strip() != PREVIEW_CONTRACT_VIOLATION_CODE:
            continue
        preview_contract_payload = payload.get("preview_contract")
        reason_code: str | None = None
        detail: str | None = None
        repair_attempted = False
        repair_succeeded = False
        if isinstance(preview_contract_payload, dict):
            reason_code_value = preview_contract_payload.get("reason_code")
            if isinstance(reason_code_value, str) and reason_code_value.strip():
                normalized_reason_code = reason_code_value.strip()
                if is_preview_contract_reason_code(normalized_reason_code):
                    reason_code = normalized_reason_code
            detail_value = preview_contract_payload.get("detail")
            if isinstance(detail_value, str) and detail_value.strip():
                detail = detail_value.strip()
            repair_attempted_value = preview_contract_payload.get("repair_attempted")
            if isinstance(repair_attempted_value, bool):
                repair_attempted = repair_attempted_value
            repair_succeeded_value = preview_contract_payload.get("repair_succeeded")
            if isinstance(repair_succeeded_value, bool):
                repair_succeeded = repair_succeeded_value
        return PreviewContractFeedback(
            assistant_at_ms=int(timestamp_value),
            assistant_turn_at_ms=int(assistant_turn_value),
            code=PREVIEW_CONTRACT_VIOLATION_CODE,
            reason_code=reason_code,
            detail=detail,
            repair_attempted=repair_attempted,
            repair_succeeded=repair_succeeded,
        )
    return None
