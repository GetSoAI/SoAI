"""SoAI - MCP utility tool: notify_user [backend/mcp/tools/notify_user.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.notifications.notification_contracts import (
    NotificationLinkType,
    NotificationType,
)
from core.notifications.notification_link_validation import validate_notification_link
from core.notifications.notification_record_models import NotificationLink
from core.notifications.notification_text_models import notification_text_from_plain
from core.types.json import is_json_dict
from mcp.tools.argument_fields import (
    optional_string,
    reject_unexpected_parameters,
    require_non_empty_string,
)
from mcp.tools.argument_runtime import require_authenticated_user_id
from mcp.tools.error import MCPToolError, get_arg
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("tool_notify_user",)

_ALLOWED_KEYS: frozenset[str] = frozenset({"type", "title", "message", "source", "link"})
_ALLOWED_LINK_KEYS: frozenset[str] = frozenset({"link_type", "value"})


def _parse_notification_type(value: JSONValue) -> NotificationType:
    normalized = require_non_empty_string(value, key="type").lower()
    try:
        return NotificationType(normalized)
    except ValueError as exception:
        raise MCPToolError(
            -32602,
            "type must be one of: info, success, warning, error",
        ) from exception


def _parse_link(value: JSONValue) -> NotificationLink | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise MCPToolError(-32602, "link must be an object when provided")
    unexpected = [key for key in value if key not in _ALLOWED_LINK_KEYS]
    if unexpected:
        unexpected_sorted = ", ".join(sorted(str(key) for key in unexpected))
        raise MCPToolError(-32602, f"Unexpected link parameter(s): {unexpected_sorted}")
    link_type_value = value.get("link_type")
    raw_link_type = require_non_empty_string(link_type_value, key="link.link_type").lower()
    try:
        link_type = NotificationLinkType(raw_link_type)
    except ValueError as exception:
        raise MCPToolError(
            -32602,
            "link.link_type must be one of: url, conversation, automation_run",
        ) from exception
    link_value = require_non_empty_string(value.get("value"), key="link.value")
    try:
        return validate_notification_link(link_type, link_value)
    except (ValidationError, ValueError) as exception:
        raise MCPToolError(-32602, str(exception)) from exception


async def tool_notify_user(utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    reject_unexpected_parameters(arguments, _ALLOWED_KEYS)
    user_id = require_authenticated_user_id(utility_tools, tool_name="notify_user")
    notification_type = _parse_notification_type(get_arg(arguments, "type"))
    title = require_non_empty_string(get_arg(arguments, "title"), key="title")
    message = require_non_empty_string(get_arg(arguments, "message"), key="message")
    source = optional_string(arguments.get("source"), key="source")
    link = _parse_link(arguments.get("link"))
    created = await utility_tools.database_notifications.create_notification(
        user_id=user_id,
        notification_type=notification_type,
        title=notification_text_from_plain(title),
        message=notification_text_from_plain(message),
        source=source,
        link=link,
    )
    payload = created.model_dump(mode="json")
    if not is_json_dict(payload):
        raise MCPToolError(-32603, "notify_user created an invalid notification payload.")
    return {"notification": payload}
