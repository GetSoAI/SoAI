"""SoAI - Conversation model_settings MCP normalization [backend/features/api/runtime/model_settings_mcp.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent_mcp_config import normalize_conversation_mcp_config
from core.automation.automation_mcp_config import normalize_automation_mcp_config
from core.conversations.conversation_mcp_extensions import (
    normalize_conversation_mcp_extensions,
)
from core.errors.exceptions import ValidationError
from core.mcp.agent_config_normalization import (
    build_normalized_agent_mcp_config_payload,
)
from core.model_settings.normalization import normalize_model_selection_settings
from core.runtime.protocols import RequestProtocol
from core.types.json_value import coerce_json_dict
from features.api.runtime.errors import (
    raise_invalid_request,
    raise_server_error,
)
from features.api.runtime.validation import (
    require_conversation_model_settings_payload,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "normalize_model_settings_mcp",
    "normalize_model_settings_mcp_for_owner",
)


def normalize_model_settings_mcp_for_owner(
    request: RequestProtocol,
    model_settings_value: JSONValue,
    *,
    is_automation: bool,
    disallowed_unqualified_tools: tuple[str, ...],
) -> JSONDict:
    model_settings = require_conversation_model_settings_payload(request, model_settings_value)
    normalized_model_settings = normalize_model_selection_settings(dict(model_settings))
    mcp_payload = _read_optional_mcp_payload(request, normalized_model_settings)
    normalized_model_settings["mcp"] = (
        normalize_automation_mcp_config(
            mcp_payload,
            disallowed_unqualified_tools=disallowed_unqualified_tools,
        )
        if is_automation
        else _normalize_conversation_mcp_config(request, mcp_payload)
    )
    return normalized_model_settings


def normalize_model_settings_mcp(
    request: RequestProtocol,
    model_settings_value: JSONValue,
) -> JSONDict:
    return normalize_model_settings_mcp_for_owner(
        request,
        model_settings_value,
        is_automation=False,
        disallowed_unqualified_tools=(),
    )


def _normalize_conversation_mcp_config(
    request: RequestProtocol,
    mcp_payload: JSONDict,
) -> JSONDict:
    try:
        normalized_mcp = normalize_conversation_mcp_config(mcp_payload)
        normalized_payload = build_normalized_agent_mcp_config_payload(normalized_mcp)
        normalized_payload.update(normalize_conversation_mcp_extensions(mcp_payload))
        return normalized_payload
    except ValidationError as exception:
        raise_invalid_request(request, exception.message)


def _read_optional_mcp_payload(
    request: RequestProtocol,
    model_settings: JSONDict,
) -> JSONDict:
    mcp_value = model_settings.get("mcp")
    if mcp_value is None:
        return {}
    mcp_payload = coerce_json_dict(mcp_value)
    if mcp_payload is None:
        raise_server_error(request, "Conversation field 'model_settings.mcp' is invalid.")
    return mcp_payload
