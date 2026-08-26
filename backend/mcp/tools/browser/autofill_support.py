"""SoAI - Browser tools: autofill argument and locator helpers [backend/mcp/tools/browser/autofill_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.web.site_scope import normalize_url
from mcp.tools.argument_fields import require_non_empty_string
from mcp.tools.browser.ref_lookup import locator_by_ref, resolve_ref_mapping
from mcp.tools.error import MCPToolError, get_arg

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page

    from core.types.json import JSONDict
    from mcp.tools.browser.types import BrowserSessionState

__all__ = (
    "PasswordFieldNotFoundError",
    "fill_fields",
    "heuristic_password_locator",
    "heuristic_username_locator",
    "require_same_origin",
    "require_text_argument",
    "require_typeable_ref",
)


class PasswordFieldNotFoundError(MCPToolError): ...


def require_text_argument(arguments: JSONDict, key: str) -> str:
    return require_non_empty_string(get_arg(arguments, key), key=key)


def require_secret_handle_argument(arguments: JSONDict, key: str = "secret_handle") -> str:
    raw = get_arg(arguments, key)
    text = raw.strip() if isinstance(raw, str) else ""
    if text:
        return text
    raise MCPToolError(
        -32602,
        "secret_handle must be a non-empty string. Call vault_secret_request or vault_login_request to obtain a secret_handle, then pass it here.",
    )


def require_credential_id_argument(arguments: JSONDict, key: str = "credential_id") -> str:
    raw = get_arg(arguments, key)
    text = raw.strip() if isinstance(raw, str) else ""
    if text:
        return text
    raise MCPToolError(
        -32602,
        "credential_id must be a non-empty string. Call vault_login_request and choose to save to the vault to obtain a credential_id, then pass it here.",
    )


def require_same_origin(*, claimed_url: str, actual_url: str) -> None:
    try:
        claimed_origin = normalize_url(claimed_url).origin
        actual_origin = normalize_url(actual_url).origin
    except ValueError as exception:
        raise MCPToolError(-32602, str(exception)) from exception
    if claimed_origin != actual_origin:
        raise MCPToolError(
            -32602,
            "Claimed url does not match the browser's current page origin; re-approval is required.",
        )


def require_typeable_ref(
    state: BrowserSessionState,
    page: Page,
    ref: str,
    *,
    field: str,
) -> Locator:
    role, _name, _nth, _frame_path = resolve_ref_mapping(state, page, ref)
    if role not in {"textbox", "searchbox", "combobox"}:
        raise MCPToolError(
            -32602,
            f"{field} must reference a typeable element role (textbox/searchbox/combobox).",
        )
    return locator_by_ref(state, page, ref)


async def heuristic_password_locator(page: Page) -> Locator:
    password_locator = page.locator("input[type='password']")
    count = await password_locator.count()
    if count == 1:
        return password_locator.first
    if count == 0:
        raise PasswordFieldNotFoundError(
            -32602,
            "No password field found. Call browser_snapshot and provide password_ref.",
        )
    raise MCPToolError(
        -32602,
        "Multiple password fields found. Call browser_snapshot and provide password_ref.",
    )


async def heuristic_username_locator(page: Page) -> Locator | None:
    username_locator = page.locator(
        "input[autocomplete='username'], input[type='email'], input[autocomplete='email']",
    )
    count = await username_locator.count()
    if count == 1:
        return username_locator.first
    if count == 0:
        return None
    raise MCPToolError(
        -32602,
        "Multiple username fields found. Call browser_snapshot and provide username_ref.",
    )


async def fill_fields(
    *,
    username_locator: Locator | None,
    password_locator: Locator | None,
    username_plaintext: str | None,
    password_plaintext: str,
    submit: bool,
) -> bool:
    if username_locator is not None and username_plaintext:
        await username_locator.fill(username_plaintext)
    if password_locator is not None:
        await password_locator.fill(password_plaintext)
    if submit:
        if password_locator is not None:
            await password_locator.press("Enter")
        elif username_locator is not None:
            await username_locator.press("Enter")
        else:
            raise MCPToolError(-32603, "Autofill submit failed: no field was filled.")
    return bool(submit)
