"""SoAI - API runtime audit logging helpers [backend/features/api/runtime/audit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from collections.abc import Mapping

from core.logging.trace import get_logger
from core.network.hosts import anonymize_ip
from core.runtime.protocols import RequestProtocol
from core.types.json import JSONDict, JSONValue
from core.validation.integers import is_strict_int
from features.api.runtime.context import require_request_context
from features.api.runtime.metadata_values import sanitize_dict_for_logging

__all__ = ("log_audit_event",)

LOGGER_NAME = "SoAI.features.api.audit"


AUDIT_INFO_PREFIXES: tuple[str, ...] = ("SYSTEM_",)
AUDIT_INFO_ACTIONS = frozenset(
    (
        "FACTORY_RESET_INITIATED",
        "RESET_CONFIGURATION",
        "CREATE_USER",
        "CHANGE_OWN_PASSWORD",
        "CHANGE_USER_PASSWORD",
        "UPDATE_USER_ROLE",
        "DELETE_USER",
        "PATCH_CONFIG",
        "RESET_METRICS",
        "RESET_CANCELLATION_REGISTRY",
        "SWEEP_CANCELLATION_REGISTRY",
        "CANCEL_REQUEST",
        "APPLY_GPU_SETTINGS_DIRECT",
        "SET_GPU_SETTINGS",
        "STORE_GPU_SLOT",
        "APPLY_GPU_SLOT",
        "TOGGLE_GPU_SLOT_BOOT",
        "CLEAR_GPU_SLOT",
        "UPLOAD_PLUGIN",
        "DOWNLOAD_PLUGIN",
        "TRIGGER_MODEL_DISCOVERY",
        "STOP_ALL_PLUGINS",
        "KILL_PROCESS",
        "RESTART_APPLICATION",
        "CREATE_PROVIDER",
        "UPDATE_PROVIDER",
        "DELETE_PROVIDER",
        "TRIGGER_SELF_UPDATE",
        "UNLOAD_ALL_MODELS_VIA_API",
        "EXECUTE_TERMINAL_COMMAND",
        "CREATE_OPENAI_API_KEY",
        "REVOKE_OPENAI_API_KEY",
        "DELETE_OPENAI_API_KEY",
        "PURGE_OPENAI_API_KEYS",
        "RESET_HARDWARE_HISTORY",
        "RESET_PREFERENCES",
        "MCP_SERVER_ADDED",
        "MCP_SERVER_REMOVED",
        "MCP_SERVER_CONNECTED",
        "MCP_SERVER_DISCONNECTED",
        "MCP_SERVER_UPDATED",
        "MCP_TOOL_INVOKED",
        "MCP_SEARCH_API_KEY_SET",
        "MCP_SEARCH_API_KEY_DELETED",
    ),
)


def log_audit_event(
    request: RequestProtocol,
    action: str,
    target: str,
    details: Mapping[str, JSONValue] | None = None,
) -> None:
    audit_logger = get_logger(LOGGER_NAME)
    context = require_request_context(request)
    try:
        auth_method = request.state.auth_method
    except AttributeError:
        auth_method = None
    try:
        user: JSONDict | None = request.state.user
    except AttributeError:
        user = None
    try:
        token_payload: JSONDict | None = request.state.token_payload
    except AttributeError:
        token_payload = None
    actor_components: list[str] = []
    if isinstance(user, dict):
        username_value = user.get("username")
        if isinstance(username_value, str) and username_value.strip():
            actor_components.append(f"user:{username_value.strip()}")
        user_id_value = user.get("id")
        if is_strict_int(user_id_value) and user_id_value > 0:
            actor_components.append(f"user_id:{user_id_value}")
    if isinstance(auth_method, str) and auth_method.strip():
        actor_components.append(f"auth:{auth_method.strip()}")
    if isinstance(token_payload, dict):
        key_id_value = token_payload.get("key_id")
        if isinstance(key_id_value, str) and key_id_value.strip():
            actor_components.append(f"key_id:{key_id_value.strip()}")
    try:
        client_ip = context.client_ip
    except AttributeError:
        client_ip = None
    if client_ip:
        actor_components.append(f"ip:{anonymize_ip(client_ip)}")
    actor = ";".join(actor_components) if actor_components else "user_unknown"
    sanitized_details = sanitize_dict_for_logging(details) if details else {}
    payload: JSONDict = {
        "actor": actor,
        "action": action,
        "target": target,
        "details": sanitized_details,
    }
    level = (
        logging.INFO
        if action in AUDIT_INFO_ACTIONS or action.startswith(AUDIT_INFO_PREFIXES)
        else logging.DEBUG
    )
    audit_logger.log(level, payload)
