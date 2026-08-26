"""SoAI - User object coercion [backend/features/api/runtime/user_coercion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.validation.integers import is_non_negative_strict_int
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX
from features.api.runtime.user_types import CurrentUser

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("coerce_current_user", "current_user_to_json_dict")


def coerce_current_user(raw: Mapping[str, JSONValue]) -> CurrentUser | None:
    if not isinstance(raw, Mapping):
        return None
    raw_id = raw.get("id")
    if not is_non_negative_strict_int(raw_id):
        return None
    username_value = raw.get("username")
    username = username_value if isinstance(username_value, str) else ""
    is_admin_value = raw.get("is_admin")
    is_admin = is_admin_value if isinstance(is_admin_value, bool) else False
    user: CurrentUser = {"id": raw_id, "is_admin": is_admin}
    if username:
        user["username"] = username
    workspace_value = raw.get("workspace_path")
    if isinstance(workspace_value, str) and workspace_value.strip():
        user["workspace_path"] = workspace_value
    default_workspace_value = raw.get("default_workspace_path")
    if isinstance(default_workspace_value, str) and default_workspace_value:
        user["default_workspace_path"] = default_workspace_value
    identity_revision_value = raw.get("identity_revision")
    if (
        isinstance(identity_revision_value, int)
        and not isinstance(identity_revision_value, bool)
        and 1 <= identity_revision_value <= JAVASCRIPT_SAFE_INTEGER_MAX
    ):
        user["identity_revision"] = identity_revision_value
    return user


def current_user_to_json_dict(user: CurrentUser) -> JSONDict:
    result: JSONDict = {
        "id": user["id"],
        "is_admin": user["is_admin"],
    }
    username = user.get("username")
    if username is not None:
        result["username"] = username
    workspace_path = user.get("workspace_path")
    if workspace_path is not None:
        result["workspace_path"] = workspace_path
    default_workspace_path = user.get("default_workspace_path")
    if default_workspace_path is not None:
        result["default_workspace_path"] = default_workspace_path
    identity_revision = user.get("identity_revision")
    if identity_revision is not None:
        result["identity_revision"] = identity_revision
    return result
