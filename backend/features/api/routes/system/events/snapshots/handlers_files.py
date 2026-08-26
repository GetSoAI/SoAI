"""SoAI - Snapshot handlers for file explorer resources [backend/features/api/routes/system/events/snapshots/handlers_files.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import WebSocket

from core.errors.exceptions import ValidationError
from core.files.protocols_explorer import FileSystemRootScopeProtocol
from core.validation.coercion import (
    coerce_int_from_numberish,
    coerce_non_negative_int_from_numberish,
)
from core.validation.integers import is_strict_int
from core.workspaces.user_workspace_path import (
    require_authenticated_user_workspace_path,
    resolve_user_record_workspace_access,
)
from features.api.routes.file_explorer.listing_serialization import (
    serialize_list_result,
)
from features.api.streaming.websocket import WebsocketConnection

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("snapshot_file_explorer_list",)


async def snapshot_file_explorer_list(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    path = data.get("path")
    if not isinstance(path, str):
        path = "/"
    offset = data.get("offset", 0)
    limit = data.get("limit")
    file_explorer_core = connection.api_context.dependencies.file_explorer_core
    if not file_explorer_core:
        raise ValidationError("File explorer service is not available.")
    if not isinstance(connection.user, dict):
        raise ValidationError("Authenticated user payload is invalid.")
    user_id_value = connection.user.get("id")
    if not is_strict_int(user_id_value):
        raise ValidationError("Authenticated user payload is invalid.")
    user_id = int(user_id_value)
    db_user = (
        await connection.api_context.dependencies.webui_manager.database_users.get_human_user_by_id(
            user_id,
        )
    )
    if not db_user:
        raise ValidationError("Authenticated user not found.")
    resolve_user_record_workspace_access(
        connection.api_context.dependencies.files,
        db_user,
    )
    workspace_path = db_user.get("workspace_path")
    workspace_path = require_authenticated_user_workspace_path(workspace_path)
    root_scope: FileSystemRootScopeProtocol = file_explorer_core.create_workspace_scope(
        workspace_path,
    )
    if isinstance(offset, float) and not offset.is_integer():
        offset_int = 0
    else:
        offset_int = coerce_non_negative_int_from_numberish(offset)
    if isinstance(limit, float) and not limit.is_integer():
        limit_int = None
    else:
        raw_limit = coerce_int_from_numberish(limit)
        limit_int = raw_limit if raw_limit is not None and raw_limit > 0 else None
    result = await file_explorer_core.list_directory(
        root_scope,
        path,
        offset=offset_int,
        limit=limit_int,
    )
    payload = serialize_list_result(result)
    payload["workspace_path_resolved"] = root_scope.root_path
    return payload
