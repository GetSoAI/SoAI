"""SoAI - MCP ripgrep argv construction for grep_files [backend/mcp/tools/grep_ripgrep_arguments.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from mcp.tools.grep_types import (
    DEFAULT_EXCLUDE_GLOBS,
    RIPGREP_MAX_FILESIZE_ARG,
    GrepRequest,
)

__all__ = (
    "build_base_ripgrep_args",
    "resolve_search_target",
)


def build_base_ripgrep_args(binary_path: str, request: GrepRequest) -> list[str]:
    args: list[str] = [
        binary_path,
        "--no-config",
        "--no-ignore",
        "--no-messages",
        "--max-filesize",
        RIPGREP_MAX_FILESIZE_ARG,
        "--glob",
        "!**/.git/**",
    ]
    if request.apply_default_excludes:
        for glob in DEFAULT_EXCLUDE_GLOBS:
            if glob == "!**/.git/**":
                continue
            args.extend(["--glob", glob])
    if request.include is not None and request.include.strip():
        args.extend(["--glob", request.include.strip()])
    if request.file_type is not None:
        args.extend(["--type", request.file_type])
    if request.case_insensitive:
        args.append("-i")
    return args


def resolve_search_target(request: GrepRequest) -> str:
    return request.candidate_file or request.search_root
