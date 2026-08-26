"""SoAI - MCP utility tool: vault_login_request [backend/mcp/tools/vault_login_request.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from core.logging.trace import get_logger
from core.web.site_scope import site_scope_from_url
from core.web.site_scope_codec import coerce_site_scope_json_dict
from mcp.tools.argument_fields import (
    optional_string,
    reject_unexpected_parameters,
    require_non_empty_string,
)
from mcp.tools.browser.autofill_support import require_same_origin
from mcp.tools.browser.session_access import require_current_page, require_session
from mcp.tools.browser.session_sync import sync_session_state
from mcp.tools.elicitation_task_lifecycle import wait_for_elicitation_task_completion
from mcp.tools.error import MCPToolError, get_arg
from mcp.tools.openai_owner_context import require_openai_conversation_owner
from mcp.tools.vault_secret_request_models import (
    decode_vault_secret_request_task_completion,
    require_vault_secret_request_scope_or_fail,
)
from mcp.tools.vault_secret_request_task_lifecycle import (
    OPERATION,
    OPERATION_NOTIFICATION_CLEANUP,
    create_vault_secret_request_task,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_vault_login_request",)

LOGGER_NAME = "SoAI.mcp.tools.vault_login_request"


def _build_title_message(label_suggestion: str | None) -> tuple[str, str]:
    if label_suggestion is not None:
        cleaned = label_suggestion.strip()
        if cleaned:
            return ("Login", f"Enter credentials for {cleaned}.")
    return ("Login", "Enter credentials to continue.")


async def _wait_for_task(
    utility_tools: MCPUtilityToolsProtocol,
    logger: LoggerProtocol,
    *,
    task_id: str,
    conv_id: str,
    expires_at_ms: int | None,
) -> JSONDict:
    completed = await wait_for_elicitation_task_completion(
        utility_tools,
        interaction_type="vault_secret_request",
        operation=OPERATION,
        operation_notification_cleanup=OPERATION_NOTIFICATION_CLEANUP,
        task_id=task_id,
        conv_id=conv_id,
        expires_at_ms=expires_at_ms,
        logger=logger,
    )
    if completed is None:
        raise MCPToolError(-32603, "vault_login_request task not found.")
    scope = require_vault_secret_request_scope_or_fail(completed.metadata)
    decoded = await decode_vault_secret_request_task_completion(utility_tools, completed)
    secret_handle_value = decoded.get("secret_handle")
    secret_handle = secret_handle_value.strip() if isinstance(secret_handle_value, str) else ""
    if not secret_handle:
        raise MCPToolError(-32603, "vault_login_request task did not produce a secret_handle.")
    saved_value = decoded.get("saved_credential_id")
    saved_credential_id = saved_value.strip() if isinstance(saved_value, str) else None
    scope_payload = coerce_site_scope_json_dict(scope)
    return {
        "secret_handle": secret_handle,
        "scope": scope_payload,
        "saved": bool(saved_credential_id),
        "credential_id": saved_credential_id or None,
    }


async def tool_vault_login_request(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    reject_unexpected_parameters(arguments, {"url", "label_suggestion", "profile", "session_scope"})
    owner_key = utility_tools.runtime_sessions.current_owner_key()
    user_id, conv_id = require_openai_conversation_owner(owner_key, tool_name="vault_login_request")
    claimed_page_url = require_non_empty_string(get_arg(arguments, "url"), key="url")
    label_suggestion = optional_string(arguments.get("label_suggestion"), key="label_suggestion")
    title, message = _build_title_message(label_suggestion)
    _store, state = await require_session(utility_tools, arguments)
    async with state.lock:
        await sync_session_state(utility_tools.config, state)
        page = require_current_page(state)
        actual_page_url = str(page.url or "").strip()
        actual_scheme = urlsplit(actual_page_url).scheme.strip().lower()
        if actual_scheme not in {"http", "https"}:
            raise MCPToolError(
                -32602,
                "vault_login_request requires the browser to be on an http(s) page.",
            )
        require_same_origin(claimed_url=claimed_page_url, actual_url=actual_page_url)
    try:
        scope = site_scope_from_url(actual_page_url)
    except ValueError as exception:
        raise MCPToolError(-32602, str(exception)) from exception
    task = await create_vault_secret_request_task(
        utility_tools,
        user_id=user_id,
        conv_id=conv_id,
        current_page_url=actual_page_url,
        title=title,
        message=message,
        allow_save_to_vault=True,
        save_label_default=label_suggestion,
    )
    logger = get_logger(LOGGER_NAME)
    result = await _wait_for_task(
        utility_tools,
        logger,
        task_id=task.task_id,
        conv_id=conv_id,
        expires_at_ms=task.ttl_expires_at_ms,
    )
    result["scope"] = coerce_site_scope_json_dict(scope)
    return result
