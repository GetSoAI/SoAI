"""SoAI - Browser tool secret_handle scope resolution [backend/mcp/tools/browser/secret_handle_scope.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.web.site_scope import SiteScope
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.secrets.handle_store import SecretHandleStore

__all__ = ("require_secret_handle_scope",)


def require_secret_handle_scope(
    secret_handle_store: SecretHandleStore,
    *,
    user_id: int,
    conv_id: str,
    secret_handle: str,
) -> SiteScope:
    scope = secret_handle_store.get_handle_scope(user_id, conv_id, secret_handle)
    if scope is None:
        raise MCPToolError(-32602, "secret_handle is invalid or expired.")
    return scope
