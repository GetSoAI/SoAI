"""SoAI - Chat template role policy SDK exports [backend/plugin_sdk/contracts/chat_template_role_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.openai.chat_template_role_policy import (
    SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER,
    normalize_openai_messages_for_chat_template_role_policy,
    normalize_openai_responses_input_for_chat_template_role_policy,
    prepare_openai_request_for_chat_template_role_policy,
    strip_soai_internal_chat_template_parameters,
)

__all__ = (
    "SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER",
    "normalize_openai_messages_for_chat_template_role_policy",
    "normalize_openai_responses_input_for_chat_template_role_policy",
    "prepare_openai_request_for_chat_template_role_policy",
    "strip_soai_internal_chat_template_parameters",
)
