"""SoAI - Shared text file extension classification [backend/core/files/text_extensions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.files.text_extensions_programming import TEXT_EXTENSIONS_PROGRAMMING
from core.files.text_extensions_supplemental import TEXT_EXTENSIONS_SUPPLEMENTAL

__all__ = (
    "CONFIG_EXTENSIONS",
    "DATA_TEXT_EXTENSIONS",
    "MARKDOWN_EXTENSIONS",
    "SHELL_SCRIPT_EXTENSIONS",
    "TEXT_EXTENSIONS",
    "resolve_text_file_content_type_from_extension",
    "resolve_text_file_content_type_from_name",
)

CONFIG_EXTENSIONS: frozenset[str] = frozenset(
    (
        "cfg",
        "conf",
        "config",
        "ini",
        "toml",
        "xml",
        "yaml",
        "yml",
    ),
)
DATA_TEXT_EXTENSIONS: frozenset[str] = frozenset(("jsonl", "ndjson"))
MARKDOWN_EXTENSIONS: frozenset[str] = frozenset(("markdown", "md", "mdx"))
SHELL_SCRIPT_EXTENSIONS: frozenset[str] = frozenset(
    (
        "bash",
        "bat",
        "cmd",
        "csh",
        "dash",
        "fish",
        "ksh",
        "ps1",
        "psm1",
        "sh",
        "tcsh",
        "zsh",
    ),
)
TEXT_EXTENSIONS: frozenset[str] = frozenset(
    (*TEXT_EXTENSIONS_PROGRAMMING, *TEXT_EXTENSIONS_SUPPLEMENTAL),
)

TEXT_EXTENSION_CONTENT_TYPES: tuple[tuple[str, str], ...] = (
    ("csv", "text/csv"),
    ("htm", "text/html"),
    ("html", "text/html"),
    ("json", "application/json"),
    ("jsonl", "application/jsonl"),
    ("markdown", "text/markdown"),
    ("md", "text/markdown"),
    ("mdx", "text/markdown"),
    ("ndjson", "application/x-ndjson"),
    ("bash", "text/x-shellscript"),
    ("bat", "text/x-shellscript"),
    ("cmd", "text/x-shellscript"),
    ("csh", "text/x-shellscript"),
    ("dash", "text/x-shellscript"),
    ("fish", "text/x-shellscript"),
    ("ksh", "text/x-shellscript"),
    ("ps1", "text/x-shellscript"),
    ("psm1", "text/x-shellscript"),
    ("sh", "text/x-shellscript"),
    ("tcsh", "text/x-shellscript"),
    ("zsh", "text/x-shellscript"),
    ("txt", "text/plain"),
    ("xhtml", "application/xhtml+xml"),
    ("xml", "application/xml"),
    ("yaml", "application/x-yaml"),
    ("yml", "application/x-yaml"),
)


def _normalize_text_file_extension(extension: str) -> str:
    return extension.strip().lower().removeprefix(".")


def resolve_text_file_content_type_from_extension(extension: str) -> str | None:
    normalized = _normalize_text_file_extension(extension)
    if not normalized or normalized not in TEXT_EXTENSIONS:
        return None
    for extension_name, content_type in TEXT_EXTENSION_CONTENT_TYPES:
        if extension_name == normalized:
            return content_type
    return "text/plain"


def resolve_text_file_content_type_from_name(name: str) -> str | None:
    normalized_name = name.strip().replace("\\", "/")
    basename = os.path.basename(normalized_name).lower()
    if not basename:
        return None
    direct_match = resolve_text_file_content_type_from_extension(basename.lstrip("."))
    if direct_match is not None:
        return direct_match
    _root, extension = os.path.splitext(basename)
    if not extension:
        return None
    return resolve_text_file_content_type_from_extension(extension)
