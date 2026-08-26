"""SoAI - MCP grep_files data contract [backend/mcp/tools/grep_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = (
    "DEFAULT_EXCLUDE_GLOBS",
    "DEFAULT_PER_FILE_COUNT",
    "DEFAULT_SEARCH_LIMIT",
    "FILE_TYPE_VALID_PATTERN",
    "MAX_CONTEXT_LINES",
    "MAX_PER_FILE_COUNT",
    "MAX_SEARCH_LIMIT",
    "RIPGREP_MAX_FILESIZE_ARG",
    "GrepFileMatch",
    "GrepLineHit",
    "GrepRequest",
    "GrepResult",
)

DEFAULT_SEARCH_LIMIT: int = 100
MAX_SEARCH_LIMIT: int = 2000
RIPGREP_MAX_FILESIZE_ARG: str = "4M"
MAX_CONTEXT_LINES: int = 20
MAX_PER_FILE_COUNT: int = 1000
DEFAULT_PER_FILE_COUNT: int = 50
FILE_TYPE_VALID_PATTERN: str = r"^[a-zA-Z0-9_+\-]{1,16}$"


DEFAULT_EXCLUDE_GLOBS: tuple[str, ...] = (
    "!**/.git/**",
    "!**/node_modules/**",
    "!**/dist/**",
    "!**/build/**",
    "!**/target/**",
    "!**/.next/**",
    "!**/out/**",
    "!**/coverage/**",
    "!**/__pycache__/**",
    "!**/.mypy_cache/**",
    "!**/.pytest_cache/**",
    "!**/.ruff_cache/**",
    "!**/.venv/**",
    "!**/venv/**",
)


@dataclass(frozen=True, slots=True)
class GrepRequest:
    pattern: str
    include: str | None
    search_root: str
    root_for_rel: str
    candidate_file: str | None
    output_mode: str
    case_insensitive: bool
    multiline: bool
    file_type: str | None
    before_context: int
    after_context: int
    head_limit: int
    offset: int
    max_count_per_file: int
    apply_default_excludes: bool


@dataclass(frozen=True, slots=True)
class GrepLineHit:
    line_number: int
    text: str
    is_context: bool


@dataclass(frozen=True, slots=True)
class GrepFileMatch:
    path: str
    match_count: int
    lines: tuple[GrepLineHit, ...]


@dataclass(frozen=True, slots=True)
class GrepResult:
    files: tuple[GrepFileMatch, ...]
    truncated: bool
    total_matches: int
    truncated_reason: str | None
