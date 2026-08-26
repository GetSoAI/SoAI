"""SoAI - Browser tool: browser_autofill_vault [backend/mcp/tools/browser/tool_autofill_vault.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.timing.epoch import epoch_ms
from mcp.tools.argument_fields import require_allowed_keys
from mcp.tools.argument_runtime import require_authenticated_user_id
from mcp.tools.argument_scalars import parse_bool_strict_default
from mcp.tools.browser.autofill_execution import (
    BrowserAutofillCredentials,
    execute_browser_autofill_on_current_page,
)
from mcp.tools.browser.autofill_support import (
    require_credential_id_argument,
    require_text_argument,
)
from mcp.tools.browser.ref_lookup import optional_ref
from mcp.tools.browser.session_access import (
    BROWSER_SESSION_PARAM_KEYS,
    require_existing_session,
)
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_browser_autofill_vault",)


async def tool_browser_autofill_vault(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=frozenset(
            {
                "url",
                "credential_id",
                "username_ref",
                "password_ref",
                "submit",
                *BROWSER_SESSION_PARAM_KEYS,
            },
        ),
        tool_name="browser_autofill_vault",
    )
    claimed_url = require_text_argument(arguments, "url")
    credential_id = require_credential_id_argument(arguments, "credential_id")
    submit = parse_bool_strict_default(arguments.get("submit"), field_name="submit", default=False)
    username_ref = optional_ref(arguments, key="username_ref")
    password_ref = optional_ref(arguments, key="password_ref")
    user_id = require_authenticated_user_id(utility_tools, tool_name="browser_autofill_vault")
    store, state = await require_existing_session(utility_tools, arguments)
    database_password_vault = utility_tools.database_password_vault
    if database_password_vault is None:
        raise MCPToolError(-32603, "Password vault is not configured.")

    async def resolve_credentials(actual_url: str) -> BrowserAutofillCredentials:
        scope, username_plaintext, password_plaintext = (
            await database_password_vault.get_credential_plaintext_for_url(
                user_id,
                credential_id,
                current_page_url=actual_url,
            )
        )
        return BrowserAutofillCredentials(
            scope=scope,
            username_plaintext=username_plaintext,
            password_plaintext=password_plaintext,
        )

    async def update_last_used() -> None:
        await database_password_vault.update_last_used(
            user_id,
            credential_id=credential_id,
            last_used_at_ms=epoch_ms(),
        )

    outcome = await execute_browser_autofill_on_current_page(
        utility_tools=utility_tools,
        store=store,
        state=state,
        claimed_url=claimed_url,
        scope_mismatch_message="Credential scope does not match the current page.",
        resolve_credentials=resolve_credentials,
        username_ref=username_ref,
        password_ref=password_ref,
        submit=submit,
        reason="browser_autofill_vault",
        post_action_lock_operation=update_last_used,
    )
    if outcome.http_auth_applied:
        return {"filled": True, "submitted": True}
    return {"filled": True, "submitted": bool(outcome.submitted)}
