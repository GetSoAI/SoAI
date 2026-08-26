"""SoAI - Tool approval permission key resolution [backend/core/tool_approval/permission_key.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.serialization.json_parsing import parse_json_value
from core.web.site_scope import site_scope_from_url

__all__ = (
    "is_tool_approval_remember_allowed",
    "require_tool_approval_remember_allowed",
    "resolve_tool_approval_permission_key",
)


def resolve_tool_approval_permission_key(
    *,
    tool_name: str,
    tool_arguments: str | None,
) -> str:
    normalized = str(tool_name or "").strip()
    if not normalized:
        return ""
    if normalized not in {"browser_autofill_secret", "browser_autofill_vault"}:
        return normalized
    if not tool_arguments:
        return f"{normalized}@unscoped"
    try:
        decoded = parse_json_value(tool_arguments)
    except ValidationError:
        return f"{normalized}@unscoped"
    if not isinstance(decoded, dict):
        return f"{normalized}@unscoped"
    url_value = decoded.get("url")
    url = url_value.strip() if isinstance(url_value, str) else ""
    if not url:
        return f"{normalized}@unscoped"
    try:
        scope = site_scope_from_url(url)
    except ValueError:
        return f"{normalized}@unscoped"
    origin = str(scope["origin"]).strip().lower()
    if not origin:
        return f"{normalized}@unscoped"
    return f"{normalized}@origin:{origin}"


def is_tool_approval_remember_allowed(*, tool_key: str) -> bool:
    normalized = str(tool_key or "").strip()
    if not normalized:
        return False
    return not normalized.endswith("@unscoped")


def require_tool_approval_remember_allowed(*, tool_key: str) -> None:
    if not is_tool_approval_remember_allowed(tool_key=tool_key):
        raise ValidationError(
            "Remember is not allowed for unscoped tool approvals. Retry with valid tool arguments.",
        )
