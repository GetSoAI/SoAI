"""SoAI - MCP file signature helpers [backend/mcp/tools/file_signatures.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat

from mcp.tools.error import MCPToolError
from mcp.tools.runtime_types import FileSignature

__all__ = ("signature_for_existing_file",)


def signature_for_existing_file(path: str, *, file_label: str) -> FileSignature:
    try:
        stat_result = os.stat(path)
    except OSError as os_exception:
        raise MCPToolError(
            -32602,
            f"Failed to stat file {file_label}: {os_exception}",
        ) from os_exception
    if not stat.S_ISREG(stat_result.st_mode):
        raise MCPToolError(-32602, f"File is not a file: {file_label}")
    return FileSignature(
        dev=int(stat_result.st_dev),
        inode=int(stat_result.st_ino),
        mtime_ns=int(stat_result.st_mtime_ns),
        size_bytes=int(stat_result.st_size),
    )
