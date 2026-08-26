"""SoAI - Effective conversation settings API projection [backend/features/api/runtime/conversation_settings_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.automation.automation_tool_blocklist import (
    load_automation_disallowed_unqualified_tools,
)
from core.conversations.settings_authority import (
    build_settings_authority_payload,
    resolve_conversation_settings_authority,
)
from core.errors.exceptions import ValidationError
from features.api.runtime.model_settings_mcp import (
    normalize_model_settings_mcp_for_owner,
)

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict

__all__ = ("project_effective_conversation_settings",)


def project_effective_conversation_settings(
    *,
    request: RequestProtocol,
    config: ConfigProtocol,
    conversation_record: JSONDict,
) -> JSONDict:
    authority = resolve_conversation_settings_authority(conversation_record)
    normalized: JSONDict = dict(conversation_record)
    normalized["model_settings"] = normalize_model_settings_mcp_for_owner(
        request,
        authority.model_settings,
        is_automation=authority.is_automation,
        disallowed_unqualified_tools=load_automation_disallowed_unqualified_tools(config),
    )
    normalized["settings_authority"] = build_settings_authority_payload(authority)
    if not isinstance(normalized.get("model_settings"), dict):
        raise ValidationError("Conversation model settings projection failed.")
    return normalized
