"""SoAI - Browser tool: browser_upload_file [backend/mcp/tools/browser/tool_upload_file.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.files.path_policy import ensure_path_within_base
from mcp.tools.argument_fields import optional_non_empty_string, require_allowed_keys
from mcp.tools.browser.ref_lookup import locator_by_ref, require_ref
from mcp.tools.browser.session_access import (
    BROWSER_SESSION_PARAM_KEYS,
    require_existing_session,
)
from mcp.tools.browser.session_action_lock import (
    finalize_locked_browser_action,
    locked_browser_action_page,
)
from mcp.tools.browser.timeouts import resolve_action_timeout_sec
from mcp.tools.error import MCPToolError, get_arg

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_browser_upload_file",)


def _require_filenames(arguments: JSONDict) -> list[str]:
    value = get_arg(arguments, "filenames")
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(entry, str) and entry.strip() for entry in value)
    ):
        raise MCPToolError(-32602, "Parameter 'filenames' must be a non-empty string array")
    if len(value) > 20:
        raise MCPToolError(-32602, "Parameter 'filenames' must have at most 20 items")
    return [str(entry).strip() for entry in value if isinstance(entry, str) and entry.strip()]


def _resolve_upload_paths(
    utility_tools: MCPUtilityToolsProtocol,
    filenames: list[str],
) -> list[str]:
    owner_key = utility_tools.runtime_sessions.current_owner_key()
    base_dir = utility_tools.runtime_sessions.require_workspace_path(owner_key)
    resolved: list[str] = []
    for filename in filenames:
        raw_name = str(filename or "").strip()
        if not raw_name:
            raise MCPToolError(-32602, "filenames entries must be non-empty strings")
        candidate: str
        if os.path.isabs(raw_name) or raw_name.startswith(("/", "\\")):
            candidate = raw_name
        else:
            candidate = os.path.join(base_dir, raw_name)
        try:
            path = ensure_path_within_base(
                base_dir,
                candidate,
                description="browser upload file",
                error_cls=ValidationError,
            )
        except ValidationError as exception:
            raise MCPToolError(-32602, str(exception)) from exception
        if not os.path.isfile(path):
            raise MCPToolError(-32602, f"Upload file not found: {raw_name}")
        resolved.append(path)
    return resolved


async def tool_browser_upload_file(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=frozenset({"element", "ref", "filenames"}) | BROWSER_SESSION_PARAM_KEYS,
        tool_name="browser_upload_file",
    )
    _store, state = await require_existing_session(utility_tools, arguments=arguments)
    _ = optional_non_empty_string(arguments.get("element"), key="element")
    ref = require_ref(arguments)
    filenames = _require_filenames(arguments)
    async with locked_browser_action_page(
        utility_tools,
        state,
        tool_name="browser_upload_file",
    ) as page:
        locator = locator_by_ref(state, page, ref)
        action_timeout_sec = resolve_action_timeout_sec(utility_tools)
        async with asyncio.timeout(float(action_timeout_sec) + 60.0):
            type_attr_raw = await locator.get_attribute("type")
            type_attr = type_attr_raw.strip().lower() if isinstance(type_attr_raw, str) else ""
            if type_attr != "file":
                raise MCPToolError(
                    -32602,
                    "browser_upload_file requires a ref to an <input type='file'> element.",
                )
            paths = _resolve_upload_paths(utility_tools, filenames)
            await locator.set_input_files(paths)
        await finalize_locked_browser_action(
            utility_tools,
            state,
            tool_name="browser_upload_file",
            persist_reason="browser_upload_file",
        )
        return {"uploaded": True, "files": list(filenames)}
