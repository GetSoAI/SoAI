"""SoAI - Browser HTTP Basic Auth helpers [backend/mcp/tools/browser/http_auth_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.async_api import HttpCredentials

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.web.site_scope import SiteScope, assert_url_allowed
from mcp.tools.argument_fields import optional_non_empty_string
from mcp.tools.argument_runtime import require_authenticated_user_id
from mcp.tools.browser.secret_handle_scope import require_secret_handle_scope
from mcp.tools.error import MCPToolError
from mcp.tools.openai_owner_context import require_openai_conversation_owner

if TYPE_CHECKING:
    from core.types.json import JSONValue
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "build_playwright_http_credentials",
    "parse_http_auth_block",
    "resolve_http_auth_credentials",
)


def parse_http_auth_block(value: JSONValue) -> tuple[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise MCPToolError(-32602, "http_auth must be an object when provided")
    secret_handle = optional_non_empty_string(
        value.get("secret_handle"),
        key="secret_handle",
    )
    credential_id = optional_non_empty_string(
        value.get("credential_id"),
        key="credential_id",
    )
    if (secret_handle is None) == (credential_id is None):
        raise MCPToolError(
            -32602,
            "http_auth must contain exactly one of: secret_handle, credential_id",
        )
    if secret_handle is not None:
        return ("secret_handle", secret_handle)
    if credential_id is None:
        raise MCPToolError(-32603, "http_auth credential_id parsing failed.")
    return ("credential_id", credential_id)


def _is_url_allowed_by_scope(url: str, scope: SiteScope) -> bool:
    try:
        assert_url_allowed(url, scope)
    except ValueError:
        return False
    return True


def _require_username(value: str | None, *, source: str) -> str:
    username = value.strip() if isinstance(value, str) else ""
    if not username:
        raise MCPToolError(
            -32602,
            f"{source} did not provide a username. HTTP Basic Auth requires both username and password.",
        )
    return username


def _require_password(value: str | None, *, source: str) -> str:
    password = value.strip() if isinstance(value, str) else ""
    if not password:
        raise MCPToolError(-32602, f"{source} did not provide a password.")
    return password


async def resolve_http_auth_credentials(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    http_auth: tuple[str, str],
    url_candidates: tuple[str, ...],
    tool_name: str,
) -> tuple[str, str]:
    auth_type, value = http_auth
    if auth_type == "secret_handle":
        owner_key = utility_tools.runtime_sessions.current_owner_key()
        user_id, conv_id = require_openai_conversation_owner(owner_key, tool_name=tool_name)
        secret_handle_store = utility_tools.secret_handle_store
        if secret_handle_store is None:
            raise MCPToolError(-32603, "Secret store is not configured.")
        scope = require_secret_handle_scope(
            secret_handle_store,
            user_id=user_id,
            conv_id=conv_id,
            secret_handle=value,
        )
        if not any(_is_url_allowed_by_scope(url, scope) for url in url_candidates if url):
            raise MCPToolError(-32602, "secret_handle scope does not match the requested URL.")
        payload = secret_handle_store.get_handle(user_id, conv_id, value, consume=True)
        if payload is None:
            raise MCPToolError(-32602, "secret_handle is invalid or expired.")
        username = _require_username(
            payload.get("username") if isinstance(payload, dict) else None,
            source="secret_handle",
        )
        password = _require_password(
            payload.get("password") if isinstance(payload, dict) else None,
            source="secret_handle",
        )
        return (username, password)

    if auth_type != "credential_id":
        raise MCPToolError(-32603, "Invalid http_auth type.")
    user_id = require_authenticated_user_id(utility_tools, tool_name=tool_name)
    vault = utility_tools.database_password_vault
    if vault is None:
        raise MCPToolError(-32603, "Password vault is not configured.")
    logger = get_logger(LOGGER_NAME)
    last_error: str | None = None
    for candidate in url_candidates:
        if not candidate:
            continue
        try:
            _scope, username_plaintext, password_plaintext = (
                await vault.get_credential_plaintext_for_url(
                    user_id,
                    credential_id=value,
                    current_page_url=candidate,
                )
            )
            username = _require_username(username_plaintext, source="credential_id")
            password = _require_password(password_plaintext, source="credential_id")
            return (username, password)
        except MCPToolError as exception:
            last_error = str(exception)
        except RECOVERABLE_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_RESOLVE_VAULT_CREDENTIAL,
            )
            log_handled_exception(
                logger,
                coerced,
                message="Failed to resolve vault credential for HTTP Basic Auth (non-critical).",
                operation=OPERATION_RESOLVE_VAULT_CREDENTIAL,
                details={"candidate_url": candidate},
                level="debug",
            )
            last_error = coerced.message
    if last_error is None:
        last_error = "credential_id could not be resolved for the requested URL."
    raise MCPToolError(-32602, last_error)


def build_playwright_http_credentials(username: str, password: str) -> HttpCredentials:
    value = username.strip()
    if not value:
        raise MCPToolError(-32602, "HTTP Basic Auth username must be non-empty.")
    return {"username": value, "password": str(password or "")}


LOGGER_NAME = "SoAI.mcp.tools.http_auth_support"
OPERATION_RESOLVE_VAULT_CREDENTIAL = "mcp.browser.http_auth_support.resolve_vault_credential"
