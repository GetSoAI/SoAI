"""SoAI - Browser tool: browser_screenshot [backend/mcp/tools/browser/tool_screenshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.files.rooted_paths import resolve_rooted_path
from core.filesystem.atomic_binary_writes import atomic_write_binary_content
from core.hardware.reservation_claims import claim_reserved_write
from core.serialization.base64_values import encode_base64_ascii
from mcp.tools.argument_fields import optional_non_empty_string, require_allowed_keys
from mcp.tools.argument_scalars import parse_bool_strict_default
from mcp.tools.browser.ref_lookup import locator_by_ref, optional_ref
from mcp.tools.browser.security_policy import require_browser_page_output_allowed
from mcp.tools.browser.session_access import (
    BROWSER_SESSION_PARAM_KEYS,
    require_existing_session,
)
from mcp.tools.browser.session_action_lock import (
    browser_action_lock,
    require_synced_browser_page_output,
)
from mcp.tools.browser.timeouts import (
    action_timeout_scope,
)
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_browser_screenshot",)

OPERATION_BROWSER_SCREENSHOT_FILE = "mcp.browser.screenshot.write_file"


def _resolve_output_target(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    filename: str,
) -> tuple[str, str]:
    owner_key = utility_tools.runtime_sessions.current_owner_key()
    base_dir = utility_tools.runtime_sessions.require_workspace_path(owner_key)
    if "\x00" in filename:
        raise MCPToolError(-32602, "filename must not contain NUL bytes.")
    try:
        target_path = resolve_rooted_path(
            filename,
            base_path=base_dir,
            description="browser screenshot output file",
            error_cls=ValidationError,
        )
    except ValidationError as exception:
        raise MCPToolError(
            -32602,
            "filename must resolve inside the current browser workspace.",
        ) from exception
    return owner_key, target_path


def _write_optional_file(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    filename: str,
    owner_key: str,
    target_path: str,
    data: bytes,
) -> None:
    required_bytes = len(data)
    details: dict[str, JSONValue] = {
        "owner_key": owner_key,
        "filename": filename.strip(),
        "required_bytes": required_bytes,
    }
    reservation = utility_tools.storage_manager.reserve_disk_space(
        path=target_path,
        required_bytes=required_bytes,
        operation=OPERATION_BROWSER_SCREENSHOT_FILE,
        details=details,
    )
    with reservation, claim_reserved_write(reservation, size_bytes=required_bytes):
        try:
            atomic_write_binary_content(target_path, data, ensure_parent=False)
        except OSError as exception:
            raise MCPToolError(
                -32603,
                "Browser screenshot output could not be written.",
                {"reason": "screenshot_write_failed"},
            ) from exception


async def tool_browser_screenshot(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=frozenset(
            {"element", "ref", "full_page", "raw", "filename", *BROWSER_SESSION_PARAM_KEYS},
        ),
        tool_name="browser_screenshot",
    )
    _store, state = await require_existing_session(utility_tools, arguments)
    _ = optional_non_empty_string(arguments.get("element"), key="element")
    ref = optional_ref(arguments)
    full_page = parse_bool_strict_default(
        arguments.get("full_page"),
        field_name="full_page",
        default=False,
    )
    raw = parse_bool_strict_default(arguments.get("raw"), field_name="raw", default=False)
    filename = optional_non_empty_string(arguments.get("filename"), key="filename")
    output_target = (
        _resolve_output_target(utility_tools, filename=filename) if filename is not None else None
    )
    async with browser_action_lock(state):
        async with state.lock:
            page = await require_synced_browser_page_output(
                utility_tools,
                state,
                tool_name="browser_screenshot",
            )
            async with action_timeout_scope(utility_tools, stabilize_ms=0, buffer_sec=30.0):
                if ref is not None:
                    locator = locator_by_ref(state, page, ref)
                    image_bytes = await locator.screenshot()
                else:
                    image_bytes = await page.screenshot(full_page=full_page, type="png")
            await require_browser_page_output_allowed(
                utility_tools,
                page,
                tool_name="browser_screenshot",
            )
        if filename is not None and output_target is not None:
            owner_key, target_path = output_target
            _write_optional_file(
                utility_tools,
                filename=filename,
                owner_key=owner_key,
                target_path=target_path,
                data=image_bytes,
            )
    encoded = encode_base64_ascii(image_bytes)
    if raw:
        return {"image_base64": encoded}
    return {"content_type": "image/png", "image_base64": encoded}
