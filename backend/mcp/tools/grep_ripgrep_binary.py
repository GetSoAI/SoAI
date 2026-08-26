"""SoAI - Managed ripgrep binary resolution for MCP grep_files [backend/mcp/tools/grep_ripgrep_binary.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.bootstrap.ripgrep_binary import ensure_ripgrep_installed, is_ripgrep_installed
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.meta.paths import get_repo_root
from mcp.tools.error import MCPToolError
from mcp.tools.offline_policy import build_offline_mode_error, is_offline_mode_enabled

if TYPE_CHECKING:
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = ("resolve_ripgrep_binary",)

LOGGER_NAME = "SoAI.mcp.tools.grep_ripgrep_binary"
OPERATION_INSTALL_RIPGREP = "mcp.tools.grep_files.ripgrep_install"


async def resolve_ripgrep_binary(runtime_flags: RuntimeFlagsViewProtocol) -> str:
    repo_root = get_repo_root()
    if is_offline_mode_enabled(runtime_flags) and not is_ripgrep_installed(repo_root):
        raise build_offline_mode_error(
            tool_name="grep_files",
            capability="managed ripgrep auto-install",
            url=None,
        )
    try:
        return await asyncio.to_thread(ensure_ripgrep_installed, repo_root)
    except RECOVERABLE_EXCEPTIONS as exception:
        logger = get_logger(LOGGER_NAME)
        coerced = coerce_to_soai_error(exception, operation=OPERATION_INSTALL_RIPGREP)
        log_exception(
            logger,
            coerced,
            message="Failed to install managed ripgrep binary.",
            operation=OPERATION_INSTALL_RIPGREP,
        )
        raise MCPToolError(
            -32603,
            f"Failed to install managed ripgrep binary: {exception}",
        ) from exception
