"""SoAI - Chat content preview feedback parsing and prompt rendering [backend/features/api/runtime/content_preview_feedback.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.conversations.assistant_turn_variant_identity import (
    require_canonical_assistant_turn_identity_epoch_ms,
)
from core.errors.exceptions import ValidationError
from core.preview_contract.preview_contract import allowed_preview_reference_types
from core.types.json_value import coerce_json_dict
from core.validation.strings import coerce_required_non_empty_str

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "ContentPreviewFeedback",
    "ContentPreviewFeedbackItem",
    "build_content_preview_feedback_system_message",
    "parse_content_preview_feedback",
)

_CONTENT_PREVIEW_FEEDBACK_PREFIX = "<soai_content_preview_feedback>"
_MAX_CONTENT_PREVIEW_ITEMS = 20
_MAX_TARGET_LENGTH = 512
_ALLOWED_STATUSES = frozenset({"failed", "disabled"})
_ALLOWED_REASON_CODES = frozenset(
    {
        "not_found",
        "access_denied",
        "invalid_reference",
        "request_failed",
        "upstream_not_found",
        "upstream_gone",
        "unsupported",
        "previews_disabled",
        "unknown",
    },
)


@dataclass(frozen=True, slots=True)
class ContentPreviewFeedbackItem:
    reference_type: str
    target: str
    status: str
    reason_code: str


@dataclass(frozen=True, slots=True)
class ContentPreviewFeedback:
    assistant_at_ms: int
    assistant_turn_at_ms: int
    items: tuple[ContentPreviewFeedbackItem, ...]


def parse_content_preview_feedback(data: JSONDict) -> ContentPreviewFeedback | None:
    raw_payload = data.get("content_preview_feedback")
    if raw_payload is None:
        return None
    payload = coerce_json_dict(raw_payload)
    if payload is None:
        raise ValidationError("content_preview_feedback must be a JSON object.")
    identity = require_canonical_assistant_turn_identity_epoch_ms(
        assistant_at_ms=payload.get("assistant_at_ms"),
        assistant_turn_at_ms=payload.get("assistant_turn_at_ms"),
        payload_label="content_preview_feedback",
    )
    items_value = payload.get("items")
    if not isinstance(items_value, list):
        raise ValidationError("content_preview_feedback.items must be an array.")
    if not items_value:
        raise ValidationError("content_preview_feedback.items must not be empty.")
    if len(items_value) > _MAX_CONTENT_PREVIEW_ITEMS:
        raise ValidationError(
            f"content_preview_feedback.items must contain at most {_MAX_CONTENT_PREVIEW_ITEMS} entries.",
        )
    items: list[ContentPreviewFeedbackItem] = []
    for index, raw_item in enumerate(items_value):
        item = coerce_json_dict(raw_item)
        if item is None:
            raise ValidationError(f"content_preview_feedback.items[{index}] must be an object.")
        items.append(_parse_content_preview_feedback_item(item=item, index=index))
    return ContentPreviewFeedback(
        assistant_at_ms=identity.assistant_at_ms,
        assistant_turn_at_ms=identity.assistant_turn_at_ms,
        items=tuple(items),
    )


def build_content_preview_feedback_system_message(
    feedback: ContentPreviewFeedback,
) -> str | None:
    if not feedback.items:
        return None
    status_lines: list[str] = []
    for item in feedback.items:
        status_label = "failed" if item.status == "failed" else "unavailable"
        reference_label = item.reference_type.replace("_", " ")
        status_lines.append(
            f"- {reference_label}: {item.target} ({status_label}; reason: {item.reason_code})",
        )
    lines = [
        _CONTENT_PREVIEW_FEEDBACK_PREFIX,
        "A prior message included WebUI preview references.",
        "Some previews failed or were unavailable in the WebUI, so the referenced content may not have been inspectable through the preview surface.",
        "Preview status:",
        *status_lines,
        "If continuing, provide corrected accessible references when possible and restate the important content directly in text instead of relying only on the preview.",
        "</soai_content_preview_feedback>",
    ]
    return "\n".join(lines)


def _parse_content_preview_feedback_item(
    *,
    item: JSONDict,
    index: int,
) -> ContentPreviewFeedbackItem:
    reference_type = coerce_required_non_empty_str(
        item.get("reference_type"),
        label=f"content_preview_feedback.items[{index}].reference_type",
    )
    status = coerce_required_non_empty_str(
        item.get("status"),
        label=f"content_preview_feedback.items[{index}].status",
    )
    reason_code = coerce_required_non_empty_str(
        item.get("reason_code"),
        label=f"content_preview_feedback.items[{index}].reason_code",
    )
    target = coerce_required_non_empty_str(
        item.get("target"),
        label=f"content_preview_feedback.items[{index}].target",
    )
    if reference_type not in allowed_preview_reference_types():
        raise ValidationError(
            f"content_preview_feedback.items[{index}].reference_type is unsupported.",
        )
    if status not in _ALLOWED_STATUSES:
        raise ValidationError(f"content_preview_feedback.items[{index}].status is unsupported.")
    if reason_code not in _ALLOWED_REASON_CODES:
        raise ValidationError(
            f"content_preview_feedback.items[{index}].reason_code is unsupported.",
        )
    if status == "disabled" and reason_code != "previews_disabled":
        raise ValidationError(
            f"content_preview_feedback.items[{index}] disabled status requires previews_disabled reason_code.",
        )
    if status == "failed" and reason_code == "previews_disabled":
        raise ValidationError(
            f"content_preview_feedback.items[{index}] failed status cannot use previews_disabled reason_code.",
        )
    if len(target) > _MAX_TARGET_LENGTH:
        raise ValidationError(f"content_preview_feedback.items[{index}].target is too long.")
    return ContentPreviewFeedbackItem(
        reference_type=reference_type,
        target=target,
        status=status,
        reason_code=reason_code,
    )
