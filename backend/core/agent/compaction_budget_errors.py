"""SoAI - Actionable agent context budget rejection [backend/core/agent/compaction_budget_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.errors.payload import ErrorPublicPayload
from core.errors.public_projection import apply_public_error_payload

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "CONTEXT_BUDGET_UNAVAILABLE_CODE",
    "ContextBudgetUnavailableError",
    "build_context_budget_unavailable_error",
)

CONTEXT_BUDGET_UNAVAILABLE_CODE = "context_budget_unavailable"
CONTEXT_BUDGET_CONFIGURATION_GUIDANCE = (
    "Increase the model context length or reduce the configured compaction output reservation."
)


class ContextBudgetUnavailableError(ValidationError):
    code: str | int = CONTEXT_BUDGET_UNAVAILABLE_CODE


def build_context_budget_unavailable_error(
    *,
    context_window_tokens: int,
    usable_context_tokens: int,
    reserved_output_tokens: int,
) -> ContextBudgetUnavailableError:
    message = (
        f"The selected model's {context_window_tokens:,}-token context leaves "
        f"{usable_context_tokens:,} usable tokens, which is too small for the configured "
        f"{reserved_output_tokens:,}-token compaction output reservation. "
        f"{CONTEXT_BUDGET_CONFIGURATION_GUIDANCE}"
    )
    details: JSONDict = {
        "type": CONTEXT_BUDGET_UNAVAILABLE_CODE,
        "context_window_tokens": int(context_window_tokens),
        "usable_context_tokens": int(usable_context_tokens),
        "reserved_output_tokens": int(reserved_output_tokens),
        "configuration_guidance": CONTEXT_BUDGET_CONFIGURATION_GUIDANCE,
    }
    error = ContextBudgetUnavailableError(message, details=details)
    apply_public_error_payload(
        error,
        ErrorPublicPayload(code=CONTEXT_BUDGET_UNAVAILABLE_CODE, message=message, details=details),
    )
    return error
