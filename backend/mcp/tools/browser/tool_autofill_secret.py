"""SoAI - Browser tool: browser_autofill_secret [backend/mcp/tools/browser/tool_autofill_secret.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.argument_fields import require_allowed_keys
from mcp.tools.argument_scalars import parse_bool_strict_default
from mcp.tools.browser.autofill_execution import (
    BrowserAutofillCredentials,
    execute_browser_autofill_on_current_page,
)
from mcp.tools.browser.autofill_support import (
    require_secret_handle_argument,
    require_text_argument,
)
from mcp.tools.browser.ref_lookup import optional_ref
from mcp.tools.browser.secret_handle_scope import require_secret_handle_scope
from mcp.tools.browser.session_access import (
    BROWSER_SESSION_PARAM_KEYS,
    require_existing_session,
)
from mcp.tools.error import MCPToolError
from mcp.tools.openai_owner_context import require_openai_conversation_owner

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_browser_autofill_secret",)


async def tool_browser_autofill_secret(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=frozenset(
            {
                "url",
                "secret_handle",
                "username_ref",
                "password_ref",
                "submit",
                *BROWSER_SESSION_PARAM_KEYS,
            },
        ),
        tool_name="browser_autofill_secret",
    )
    owner_key = utility_tools.runtime_sessions.current_owner_key()
    user_id, conv_id = require_openai_conversation_owner(
        owner_key,
        tool_name="browser_autofill_secret",
    )
    claimed_url = require_text_argument(arguments, "url")
    secret_handle = require_secret_handle_argument(arguments, "secret_handle")
    submit = parse_bool_strict_default(arguments.get("submit"), field_name="submit", default=False)
    username_ref = optional_ref(arguments, key="username_ref")
    password_ref = optional_ref(arguments, key="password_ref")
    store, state = await require_existing_session(utility_tools, arguments)
    secret_handle_store = utility_tools.secret_handle_store
    if secret_handle_store is None:
        raise MCPToolError(-32603, "Secret store is not configured.")
    secret_scope = require_secret_handle_scope(
        secret_handle_store,
        user_id=user_id,
        conv_id=conv_id,
        secret_handle=secret_handle,
    )
    payload = secret_handle_store.get_handle(
        user_id,
        conv_id,
        secret_handle,
        consume=False,
    )
    if payload is None:
        raise MCPToolError(-32602, "secret_handle is invalid or expired.")
    password_plaintext_value = payload.get("password")
    password_plaintext = (
        password_plaintext_value if isinstance(password_plaintext_value, str) else ""
    )
    if not password_plaintext:
        raise MCPToolError(-32603, "Resolved secret_handle payload is invalid.")
    username_plaintext_value = payload.get("username")
    username_plaintext = (
        username_plaintext_value.strip()
        if isinstance(username_plaintext_value, str) and username_plaintext_value.strip()
        else None
    )
    if username_ref is not None and username_plaintext is None:
        raise MCPToolError(
            -32602,
            "secret_handle did not provide a username, but username_ref was provided.",
        )
    interaction_secret_identity = secret_handle_store.get_interaction_secret_identity(
        user_id,
        conv_id,
        secret_handle,
    )
    current_tool_identity = utility_tools.active_tool_call_context.get()
    if interaction_secret_identity is not None and current_tool_identity is None:
        raise MCPToolError(-32603, "Secret-consuming tool identity is unavailable.")

    async def resolve_credentials(_actual_url: str) -> BrowserAutofillCredentials:
        return BrowserAutofillCredentials(
            scope=secret_scope,
            username_plaintext=username_plaintext,
            password_plaintext=password_plaintext,
        )

    async def forget_secret_handle() -> None:
        secret_handle_store.forget_handle(user_id, conv_id, secret_handle)

    async def mark_interaction_secret_started() -> None:
        if interaction_secret_identity is None or current_tool_identity is None:
            return
        marked = await utility_tools.task_registry.database_tasks.mark_interaction_secret_downstream_started(
            identity=interaction_secret_identity,
            tool_call_id=current_tool_identity.call_id,
        )
        if not marked:
            raise MCPToolError(-32603, "Secret handoff is no longer valid for this tool call.")

    outcome = await execute_browser_autofill_on_current_page(
        utility_tools=utility_tools,
        store=store,
        state=state,
        claimed_url=claimed_url,
        scope_mismatch_message="secret_handle scope does not match the current page.",
        resolve_credentials=resolve_credentials,
        username_ref=username_ref,
        password_ref=password_ref,
        submit=submit,
        reason="browser_autofill_secret",
        pre_action_lock_operation=mark_interaction_secret_started,
        post_action_lock_operation=forget_secret_handle,
    )
    if outcome.http_auth_applied:
        return {"filled": True, "submitted": True}
    return {"filled": True, "submitted": bool(outcome.submitted)}
