"""SoAI - Browser session access helpers [backend/mcp/tools/browser/session_access.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, NoReturn

from core.config.value_validation import is_config_dict
from core.errors.exceptions import ValidationError
from core.mcp.owner_keys import (
    build_browser_owner_key_value,
    build_openai_conversation_owner_key,
    build_openai_user_owner_key,
)
from core.users.user_id import is_strict_user_id
from mcp.tools.browser.config_paths import slugify_browser_path_token
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from playwright.async_api import Page

    from core.config.protocols import ConfigProtocol
    from core.types.json import JSONDict
    from mcp.tools.browser.internal_protocols import BrowserSessionStoreProtocol
    from mcp.tools.browser.types import BrowserSessionState
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "build_browser_owner_key",
    "clear_snapshot_refs",
    "mark_event_stream_page_load",
    "mark_page_load",
    "parse_browser_profile",
    "parse_browser_session_scope",
    "prepare_snapshot_refs",
    "require_browser_enabled",
    "require_current_page",
    "find_existing_session",
    "require_existing_session",
    "require_session",
    "resolve_browser_owner_base",
    "resolve_browser_owner_key",
    "slugify_browser_token",
)


def require_browser_enabled(utility_tools: MCPUtilityToolsProtocol) -> None:
    if not utility_tools.config.get_bool("TOOLS.MCP.BROWSER.ENABLED"):
        raise MCPToolError(
            -32603,
            "Browser tools are disabled by configuration (TOOLS.MCP.BROWSER.ENABLED=false).",
        )


BROWSER_SESSION_PARAM_KEYS: frozenset[str] = frozenset({"profile", "session_scope"})


def _raise_no_active_browser_session() -> NoReturn:
    raise MCPToolError(
        -32603,
        "No active browser session. Call browser_navigate first.",
        data={"reason": "no_active_session"},
    )


def _default_browser_profile(config: ConfigProtocol) -> str:
    value = config.get_str("TOOLS.MCP.BROWSER.DEFAULT_PROFILE") if config is not None else None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "default"


def _resolve_configured_profiles(config: ConfigProtocol) -> frozenset[str]:
    names: set[str] = {"default"}
    raw_profiles = config.get("TOOLS.MCP.BROWSER.PROFILES") if config is not None else None
    if is_config_dict(raw_profiles):
        for key in raw_profiles:
            if isinstance(key, str) and key.strip():
                names.add(key.strip())
    return frozenset(names)


def parse_browser_profile(arguments: JSONDict, *, config: ConfigProtocol) -> str:
    allowed_profiles = _resolve_configured_profiles(config)
    default_profile = _default_browser_profile(config)
    if default_profile not in allowed_profiles:
        raise MCPToolError(
            -32603,
            (
                "Browser profile configuration error: TOOLS.MCP.BROWSER.DEFAULT_PROFILE "
                "is not present in TOOLS.MCP.BROWSER.PROFILES."
            ),
        )
    raw = arguments.get("profile")
    if raw is None:
        return default_profile
    if not isinstance(raw, str) or not raw.strip():
        raise MCPToolError(-32602, "profile must be a non-empty string when provided")
    profile = raw.strip()
    if profile not in allowed_profiles:
        available_profiles = ", ".join(sorted(allowed_profiles))
        raise MCPToolError(
            -32602,
            (
                f"Unknown browser profile '{profile}'. Use browser_profiles or choose "
                f"one of: {available_profiles}"
            ),
        )
    return profile


def _default_browser_session_scope(config: ConfigProtocol) -> str:
    value = config.get_str("TOOLS.MCP.BROWSER.SESSION_SCOPE") if config is not None else None
    if not isinstance(value, str) or not value.strip():
        return "conversation"
    normalized = value.strip().lower()
    if normalized in {"conversation", "user"}:
        return normalized
    raise MCPToolError(
        -32603,
        (
            "Browser session configuration error: TOOLS.MCP.BROWSER.SESSION_SCOPE must be "
            "'conversation' or 'user'."
        ),
    )


def parse_browser_session_scope(arguments: JSONDict, *, config: ConfigProtocol) -> str:
    raw = arguments.get("session_scope")
    if raw is None:
        return _default_browser_session_scope(config)
    if not isinstance(raw, str) or not raw.strip():
        raise MCPToolError(-32602, "session_scope must be 'conversation' or 'user' when provided")
    normalized = raw.strip().lower()
    if normalized in {"conversation", "user"}:
        return normalized
    raise MCPToolError(-32602, "session_scope must be 'conversation' or 'user' when provided")


def slugify_browser_token(value: str, *, label: str) -> str:
    try:
        return slugify_browser_path_token(value, label=label)
    except ValidationError as exception:
        raise MCPToolError(-32602, str(exception)) from exception


def resolve_browser_owner_base(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    session_scope: str,
) -> str:
    identity = utility_tools.active_tool_call_context.get()
    if identity is not None and is_strict_user_id(identity.user_id):
        user_id = int(identity.user_id)
        conv_id = str(identity.conv_id or "").strip()
        if session_scope == "user":
            return build_openai_user_owner_key(user_id=user_id)
        if not conv_id:
            return build_openai_user_owner_key(user_id=user_id)
        return build_openai_conversation_owner_key(user_id=user_id, conv_id=conv_id)
    return utility_tools.browser_sessions.current_owner_key()


def build_browser_owner_key(*, owner_base: str, profile: str, session_scope: str) -> str:
    profile_slug = slugify_browser_token(profile, label="profile")
    scope_slug = slugify_browser_token(session_scope, label="session_scope")
    try:
        return build_browser_owner_key_value(
            owner_base=owner_base,
            profile_slug=profile_slug,
            session_scope_slug=scope_slug,
        )
    except ValidationError as exception:
        raise MCPToolError(-32603, str(exception)) from exception


def resolve_browser_owner_key(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    profile: str,
    session_scope: str,
) -> str:
    base = resolve_browser_owner_base(utility_tools, session_scope=session_scope)
    return build_browser_owner_key(owner_base=base, profile=profile, session_scope=session_scope)


async def require_session(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict | None = None,
) -> tuple[BrowserSessionStoreProtocol, BrowserSessionState]:
    require_browser_enabled(utility_tools)
    resolved_arguments: JSONDict = arguments or {}
    profile = parse_browser_profile(resolved_arguments, config=utility_tools.config)
    session_scope = parse_browser_session_scope(resolved_arguments, config=utility_tools.config)
    owner_base = resolve_browser_owner_base(utility_tools, session_scope=session_scope)
    owner_key = build_browser_owner_key(
        owner_base=owner_base,
        profile=profile,
        session_scope=session_scope,
    )
    store = utility_tools.browser_sessions
    state = await store.get_or_create_session(
        owner_key=owner_key,
        owner_base=owner_base,
        profile=profile,
        session_scope=session_scope,
    )
    return (store, state)


async def find_existing_session(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict | None = None,
) -> tuple[BrowserSessionStoreProtocol, BrowserSessionState] | None:
    require_browser_enabled(utility_tools)
    resolved_arguments: JSONDict = arguments or {}
    profile = parse_browser_profile(resolved_arguments, config=utility_tools.config)
    session_scope = parse_browser_session_scope(resolved_arguments, config=utility_tools.config)
    owner_base = resolve_browser_owner_base(utility_tools, session_scope=session_scope)
    owner_key = build_browser_owner_key(
        owner_base=owner_base,
        profile=profile,
        session_scope=session_scope,
    )
    store = utility_tools.browser_sessions
    create_lock: asyncio.Lock | None = None
    async with store.sessions_lock:
        state = store.sessions.get(owner_key)
        if state is not None and bool(state.context_closed):
            store.sessions.pop(owner_key, None)
            state = None
        if state is None:
            create_lock = store.owner_create_locks.get(owner_key)
    if state is not None:
        return (store, state)
    if create_lock is not None and create_lock.locked():
        async with create_lock:
            async with store.sessions_lock:
                state = store.sessions.get(owner_key)
                if state is not None and bool(state.context_closed):
                    store.sessions.pop(owner_key, None)
                    state = None
            if state is not None:
                return (store, state)
    return None


async def require_existing_session(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict | None = None,
) -> tuple[BrowserSessionStoreProtocol, BrowserSessionState]:
    result = await find_existing_session(utility_tools, arguments)
    if result is not None:
        return result
    _raise_no_active_browser_session()


def require_current_page(state: BrowserSessionState) -> Page:
    if not state.pages:
        raise MCPToolError(-32603, "Browser session is missing an active page.")
    index = state.active_index
    if index < 0 or index >= len(state.pages):
        raise MCPToolError(-32603, "Browser session active tab index is invalid.")
    return state.pages[index]


def clear_snapshot_refs(state: BrowserSessionState) -> None:
    state.refs.clear()
    state.ref_aliases.clear()
    state.ref_registry.clear()
    state.next_ref_index = 1
    state.ref_page_url = None
    state.ref_frame_tree_signature = ()
    state.last_snapshot_text = None


def prepare_snapshot_refs(state: BrowserSessionState) -> None:
    state.refs.clear()
    state.ref_aliases.clear()
    state.ref_page_url = None
    state.ref_frame_tree_signature = ()
    state.last_snapshot_text = None


def mark_event_stream_page_load(state: BrowserSessionState) -> None:
    state.console_page_load_index = len(state.console_messages) + int(state.console_queue.qsize())
    state.network_page_load_index = len(state.network_requests) + int(state.network_queue.qsize())


def mark_page_load(state: BrowserSessionState) -> None:
    mark_event_stream_page_load(state)
    clear_snapshot_refs(state)
