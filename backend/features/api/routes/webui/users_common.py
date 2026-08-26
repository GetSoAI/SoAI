"""SoAI - Shared WebUI user route helpers [backend/features/api/routes/webui/users_common.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.files.workspace_path import resolve_workspace_real_path
from core.workspaces.user_workspace_path import require_user_record_workspace_path
from features.api.runtime.users_serialization import sanitize_user_response

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = ("serialize_user_response",)


def serialize_user_response(
    api_context: ApiContext,
    user: JSONDict,
    *,
    workspace_real_path: str | None = None,
) -> JSONDict:
    sanitized = sanitize_user_response(dict(user))
    try:
        workspace_value = require_user_record_workspace_path(sanitized)
        resolved = (
            resolve_workspace_real_path(api_context.dependencies.files, workspace_value)
            if workspace_real_path is None
            else workspace_real_path
        )
    except (StateError, ValidationError) as exception:
        raise StateError("User response is missing a valid workspace_path.") from exception
    if not isinstance(resolved, str) or not resolved.strip():
        raise StateError("Resolved user workspace_path is invalid.")
    sanitized["workspace_path_resolved"] = resolved
    return sanitized
