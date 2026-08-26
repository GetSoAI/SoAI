"""SoAI - Assistant usage identity validation [backend/core/conversations/assistant_usage_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = ("validate_assistant_usage_identity",)


def validate_assistant_usage_identity(
    *,
    role: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    total_tokens: int | None,
    request_id: str | None,
    usage_source: str | None,
    context_label: str,
) -> bool:
    has_token_usage = (
        prompt_tokens is not None or completion_tokens is not None or total_tokens is not None
    )
    if not has_token_usage:
        return False
    if role != "assistant":
        raise ValidationError(
            f"{context_label} token usage fields are only supported for assistant messages.",
        )
    if prompt_tokens is None or completion_tokens is None or total_tokens is None:
        raise ValidationError(
            f"{context_label} token usage fields must be all present or all absent.",
        )
    if prompt_tokens < 0 or completion_tokens < 0 or total_tokens < 0:
        raise ValidationError(f"{context_label} token usage fields must be non-negative.")
    if total_tokens != prompt_tokens + completion_tokens:
        raise ValidationError(
            f"{context_label} field 'total_tokens' must equal prompt_tokens plus completion_tokens.",
        )
    if request_id is None:
        raise ValidationError(
            f"{context_label} field 'request_id' is required when token usage is present.",
        )
    if usage_source is None:
        raise ValidationError(
            f"{context_label} field 'usage_source' is required when token usage is present.",
        )
    return True
