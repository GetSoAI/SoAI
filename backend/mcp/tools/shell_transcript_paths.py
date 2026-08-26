"""SoAI - MCP shell transcript temp path lifecycle [backend/mcp/tools/shell_transcript_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.files.upload_policy import resolve_temp_directory_runtime
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol

__all__ = (
    "SHELL_TRANSCRIPT_TEMP_DIRNAME",
    "resolve_shell_transcript_root",
)

SHELL_TRANSCRIPT_TEMP_DIRNAME: str = "mcp-shell-transcripts"


def resolve_shell_transcript_root(config: ConfigProtocol) -> str:
    try:
        temp_dir = resolve_temp_directory_runtime(config)
    except ValidationError as exception:
        raise MCPToolError(-32603, str(exception)) from exception
    root = os.path.join(temp_dir, SHELL_TRANSCRIPT_TEMP_DIRNAME)
    os.makedirs(root, mode=0o700, exist_ok=True)
    return root
