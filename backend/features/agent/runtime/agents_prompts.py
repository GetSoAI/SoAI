"""SoAI - Agent instruction file discovery and injection [backend/features/agent/runtime/agents_prompts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.files.path_policy import ensure_path_within_base
from core.filesystem.open_files import read_regular_file_no_symlink
from core.openai.internal_message_metadata import (
    AGENT_INSTRUCTIONS_MESSAGE_TYPE,
    build_internal_system_message,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "AGENTS_FILENAME",
    "AGENT_INSTRUCTIONS_FILENAMES",
    "SOAI_FILENAME",
    "build_agents_message",
    "discover_agents_files",
    "read_agents_instructions",
)

AGENTS_FILENAME = "AGENTS.md"
SOAI_FILENAME = "SOAI.md"
AGENT_INSTRUCTIONS_FILENAMES = (SOAI_FILENAME, AGENTS_FILENAME)
AGENTS_MAX_BYTES = 262_144


def _normalize_agent_files(agent_files: list[str]) -> tuple[str, ...]:
    normalized_files: list[str] = []
    for path in agent_files:
        normalized = str(path or "").strip()
        if not normalized:
            continue
        normalized_files.append(normalized)
    if any(os.path.basename(path) == SOAI_FILENAME for path in normalized_files):
        return tuple(path for path in normalized_files if os.path.basename(path) == SOAI_FILENAME)
    return tuple(normalized_files)


def _agent_instructions_filename(path: str) -> str:
    filename = os.path.basename(path)
    if filename in AGENT_INSTRUCTIONS_FILENAMES:
        return filename
    return AGENTS_FILENAME


def _validate_discovered_agent_file(*, root: str, candidate: str, filename: str) -> str:
    if os.path.islink(candidate):
        raise ValidationError(f"{filename} must be a regular file, not a symlink: {candidate}")
    if not os.path.isfile(candidate):
        raise ValidationError(f"{filename} must be a regular file: {candidate}")
    return ensure_path_within_base(root, candidate, description=filename, error_cls=ValidationError)


def discover_agents_files(*, workspace_path: str) -> list[str]:
    normalized_root = str(workspace_path or "").strip()
    if not normalized_root:
        return []
    root = os.path.realpath(os.path.abspath(normalized_root))
    for filename in AGENT_INSTRUCTIONS_FILENAMES:
        candidate = os.path.join(root, filename)
        if not os.path.exists(candidate):
            continue
        return [
            _validate_discovered_agent_file(
                root=root,
                candidate=candidate,
                filename=filename,
            ),
        ]
    return []


def _read_agents_instructions_uncached(agent_files: tuple[str, ...]) -> str | None:
    parts: list[str] = []
    for normalized in agent_files:
        filename = _agent_instructions_filename(normalized)
        if os.path.islink(normalized):
            raise ValidationError(f"{filename} must be a regular file, not a symlink: {normalized}")
        if not os.path.isfile(normalized):
            raise ValidationError(f"{filename} must be a regular file: {normalized}")
        content_bytes = read_regular_file_no_symlink(
            normalized,
            max_bytes=AGENTS_MAX_BYTES,
            symlink_message=f"{filename} must be a regular file, not a symlink: {normalized}",
            open_message=f"Failed to read {filename}: {normalized}",
            inspect_message=f"Failed to read {filename}: {normalized}",
            regular_file_message=f"{filename} must be a regular file: {normalized}",
        )
        if len(content_bytes) > AGENTS_MAX_BYTES:
            raise ValidationError(
                f"{filename} exceeds maximum supported size ({AGENTS_MAX_BYTES} bytes).",
            )
        content = content_bytes.decode("utf-8", errors="replace").strip()
        if not content:
            continue
        sanitized = content.replace("</INSTRUCTIONS>", "")
        directory = os.path.dirname(normalized) or normalized
        content_block = f"<INSTRUCTIONS>\n{sanitized}\n</INSTRUCTIONS>"
        parts.append(f"# {filename} instructions for {directory}\n\n{content_block}")
    if not parts:
        return None
    return "\n\n".join(parts)


def read_agents_instructions(
    agent_files: list[str],
    *,
    workspace_path: str | None = None,
) -> str | None:
    _ = workspace_path
    normalized_agent_files = _normalize_agent_files(agent_files)
    return _read_agents_instructions_uncached(normalized_agent_files)


def build_agents_message(instructions: str) -> JSONDict:
    return build_internal_system_message(
        content=instructions.strip(),
        message_type=AGENT_INSTRUCTIONS_MESSAGE_TYPE,
    )
