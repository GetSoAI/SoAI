"""SoAI - Chat preview-contract violation feedback [backend/features/api/runtime/preview_contract_feedback.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.conversations.assistant_turn_variant_identity import (
    require_canonical_assistant_turn_identity_epoch_ms,
)
from core.errors.exceptions import ValidationError
from core.preview_contract.preview_contract import PREVIEW_CONTRACT_VIOLATION_CODE
from core.preview_contract.preview_contract_reason_codes import (
    is_preview_contract_reason_code,
)
from core.types.json_value import coerce_json_dict
from core.validation.strings import coerce_optional_trimmed_str
from features.api.runtime.preview_contract_persisted_feedback import (
    PreviewContractFeedback,
)
from features.api.runtime.preview_contract_retry import (
    build_preview_contract_retry_system_message,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "PreviewContractFeedback",
    "build_preview_contract_feedback_system_message",
    "parse_preview_contract_feedback",
)


def parse_preview_contract_feedback(data: JSONDict) -> PreviewContractFeedback | None:
    raw_payload = data.get("preview_contract_feedback")
    if raw_payload is None:
        return None
    payload = coerce_json_dict(raw_payload)
    if payload is None:
        raise ValidationError("preview_contract_feedback must be a JSON object.")
    identity = require_canonical_assistant_turn_identity_epoch_ms(
        assistant_at_ms=payload.get("assistant_at_ms"),
        assistant_turn_at_ms=payload.get("assistant_turn_at_ms"),
        payload_label="preview_contract_feedback",
    )
    code_value = payload.get("code")
    code = str(code_value or "").strip()
    if code != PREVIEW_CONTRACT_VIOLATION_CODE:
        raise ValidationError("preview_contract_feedback.code is unsupported.")
    reason_code = coerce_optional_trimmed_str(payload.get("reason_code"))
    if reason_code is not None and not is_preview_contract_reason_code(reason_code):
        raise ValidationError("preview_contract_feedback.reason_code is unsupported.")
    detail = coerce_optional_trimmed_str(payload.get("detail"))
    repair_attempted_value = payload.get("repair_attempted")
    if repair_attempted_value is None:
        repair_attempted = False
    elif isinstance(repair_attempted_value, bool):
        repair_attempted = repair_attempted_value
    else:
        raise ValidationError("preview_contract_feedback.repair_attempted must be a boolean.")
    repair_succeeded_value = payload.get("repair_succeeded")
    if repair_succeeded_value is None:
        repair_succeeded = False
    elif isinstance(repair_succeeded_value, bool):
        repair_succeeded = repair_succeeded_value
    else:
        raise ValidationError("preview_contract_feedback.repair_succeeded must be a boolean.")
    if repair_succeeded and not repair_attempted:
        raise ValidationError(
            "preview_contract_feedback.repair_succeeded requires repair_attempted.",
        )
    return PreviewContractFeedback(
        assistant_at_ms=identity.assistant_at_ms,
        assistant_turn_at_ms=identity.assistant_turn_at_ms,
        code=code,
        reason_code=reason_code,
        detail=detail,
        repair_attempted=repair_attempted,
        repair_succeeded=repair_succeeded,
    )


def build_preview_contract_feedback_system_message(
    feedback: PreviewContractFeedback,
) -> str | None:
    if feedback.code != PREVIEW_CONTRACT_VIOLATION_CODE:
        return None
    return build_preview_contract_retry_system_message(feedback.detail)
