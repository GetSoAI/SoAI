"""SoAI - WebSocket admin update message handlers [backend/features/api/routes/system/events/websocket_admin_updates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.state.access import AccessAction
from core.system_api.websocket_payloads import build_websocket_event_payload
from core.timing.epoch import epoch_ms
from core.types.json_value import coerce_json_dict
from core.validation.integers import is_strict_int
from core.validation.strings import coerce_optional_trimmed_str
from core.workspaces.user_workspace_path import (
    require_user_record_username,
    resolve_user_workspace_update,
)
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes
from features.api.routes.system.events.websocket_command_payloads import (
    resolve_body_or_root_value,
)
from features.api.routes.system.events.websocket_errors import (
    enqueue_websocket_error,
    enqueue_websocket_forbidden_error,
    enqueue_websocket_invalid_request_error,
    enqueue_websocket_not_found_error,
)
from features.api.routes.webui.users_common import serialize_user_response
from features.api.runtime.audit import log_audit_event
from features.api.runtime.event_enqueue import enqueue_event_or_warn

if TYPE_CHECKING:
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.runtime.context import ApiContext
    from features.api.streaming.websocket import (
        WebsocketConnection,
        WebSocketRequestAdapter,
    )

__all__ = (
    "handle_update_openai_api_key_quota",
    "handle_update_user_workspace_path",
)


async def handle_update_openai_api_key_quota(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    request: RequestProtocol,
    request_adapter: WebSocketRequestAdapter,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
) -> None:
    del request
    if AccessAction.OPENAI_API_ADMIN not in connection.granted_actions:
        await enqueue_websocket_forbidden_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
        )
        return
    key_id = coerce_optional_trimmed_str(resolve_body_or_root_value(data, "key_id"))
    if key_id is None:
        await enqueue_websocket_invalid_request_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            "update_openai_api_key_quota requires a non-empty key_id.",
        )
        return
    config_value = resolve_body_or_root_value(data, "config")
    config = coerce_json_dict(config_value)
    if config is None:
        await enqueue_websocket_invalid_request_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            "update_openai_api_key_quota requires a config object.",
        )
        return
    database_api_keys = api_context.dependencies.webui_manager.database_api_keys
    updated_config = await database_api_keys.set_quota_config(key_id, config, reset_usage=True)
    status = await database_api_keys.get_quota_status(key_id, epoch_ms())
    log_audit_event(
        request_adapter,
        "UPDATE_OPENAI_API_KEY_QUOTA",
        key_id,
        {"mode": updated_config.get("mode"), "via": "websocket"},
    )
    payload = build_websocket_event_payload(
        WebSocketEventTypes.OPENAI_API_KEY_QUOTA_UPDATED,
        {"data": {"key_id": key_id, "config": updated_config, "status": status}},
    )
    enqueue_event_or_warn(
        enqueue_warning_tracker,
        connection.queue,
        payload,
        "OpenAI API key quota updated",
    )


async def handle_update_user_workspace_path(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    request: RequestProtocol,
    request_adapter: WebSocketRequestAdapter,
    api_context: ApiContext,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
) -> None:
    del request
    if AccessAction.USER_ADMIN not in connection.granted_actions:
        await enqueue_websocket_forbidden_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
        )
        return
    user_id_value = resolve_body_or_root_value(data, "user_id")
    if not is_strict_int(user_id_value):
        await enqueue_websocket_invalid_request_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            "update_user_workspace_path requires an integer user_id.",
        )
        return
    user_id = int(user_id_value)
    if user_id <= 0:
        await enqueue_websocket_invalid_request_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            "update_user_workspace_path requires user_id > 0.",
        )
        return
    workspace_value = resolve_body_or_root_value(data, "workspace_path")
    if workspace_value is not None and not isinstance(workspace_value, str):
        await enqueue_websocket_invalid_request_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            "update_user_workspace_path requires workspace_path to be a string or null.",
        )
        return
    database_users = api_context.dependencies.webui_manager.database_users
    target_user = await database_users.get_human_user_by_id(user_id)
    if not target_user:
        await enqueue_websocket_not_found_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            "User not found.",
        )
        return
    try:
        username = require_user_record_username(target_user)
        default_workspace_path = target_user.get("default_workspace_path")
        if not isinstance(default_workspace_path, str):
            raise StateError("User record is missing default_workspace_path.")
    except StateError:
        await enqueue_websocket_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            "server_error",
            "User record is missing a username.",
            code="internal_error",
        )
        return
    try:
        resolved_update = resolve_user_workspace_update(
            api_context.dependencies.files,
            default_workspace_path=default_workspace_path,
            requested_value=workspace_value,
            require_existing_directory=True,
        )
    except ValidationError as exception:
        await enqueue_websocket_invalid_request_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            exception.message,
        )
        return
    updated_user = await database_users.update_user_workspace_path(
        user_id,
        resolved_update.workspace_path,
        resolved_update.workspace_real_path,
    )
    if updated_user is None:
        await enqueue_websocket_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            "server_error",
            "Failed to update user workspace path.",
            code="internal_error",
        )
        return
    log_audit_event(
        request_adapter,
        "UPDATE_USER_WORKSPACE_PATH",
        f"user:{username}",
        {"workspace_path": resolved_update.workspace_path, "via": "websocket"},
    )
    payload = build_websocket_event_payload(
        "user_workspace_path_updated",
        {"data": serialize_user_response(api_context, updated_user)},
    )
    enqueue_event_or_warn(
        enqueue_warning_tracker,
        connection.queue,
        payload,
        "User workspace path updated",
    )
