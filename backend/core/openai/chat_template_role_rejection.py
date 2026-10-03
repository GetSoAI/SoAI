"""SoAI - Dependency-light chat-template role rejection classification [backend/core/openai/chat_template_role_rejection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "CHAT_TEMPLATE_ROLE_REJECTION_CATEGORY",
    "CHAT_TEMPLATE_ROLE_REJECTION_CATEGORY_KEY",
    "is_chat_template_role_error_message",
)

CHAT_TEMPLATE_ROLE_REJECTION_CATEGORY_KEY = "upstream_error_category"
CHAT_TEMPLATE_ROLE_REJECTION_CATEGORY = "chat_template_role_rejection"
_ROLE_ERROR_MARKERS: tuple[str, ...] = (
    "conversation roles must alternate user/assistant/user/assistant",
    "only user, assistant and tool roles are supported",
    "unsupported role",
    "role must be",
    "got system",
)
_ROLE_PLACEMENT_SUBJECTS: tuple[str, ...] = (
    "developer message",
    "developer role",
    "system message",
    "system role",
)
_ROLE_PLACEMENT_REQUIREMENTS: tuple[str, ...] = (
    "must be at the beginning",
    "must be at the start",
    "must be first",
    "only allowed at the beginning",
    "only allowed at the start",
)


def is_chat_template_role_error_message(message: str) -> bool:
    normalized = str(message or "").strip().lower()
    if not normalized:
        return False
    has_role_placement_subject = any(subject in normalized for subject in _ROLE_PLACEMENT_SUBJECTS)
    has_role_placement_requirement = any(
        requirement in normalized for requirement in _ROLE_PLACEMENT_REQUIREMENTS
    )
    if has_role_placement_subject and has_role_placement_requirement:
        return True
    has_role_context = "role" in normalized or "jinja exception" in normalized
    if not has_role_context:
        return False
    for marker in _ROLE_ERROR_MARKERS:
        if marker in normalized:
            return True
    return False
