"""SoAI - MCP utility tool workspace path resolution [backend/mcp/tools/files_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import difflib
import os

from core.errors.exceptions import ValidationError
from core.files.path_policy import ensure_path_within_base
from core.files.rooted_paths import (
    resolve_rooted_candidate_path,
    resolve_rooted_existing_file,
    resolve_rooted_path,
)
from mcp.tools.error import MCPToolError

__all__ = (
    "build_missing_directory_error_message",
    "resolve_existing_dir_under_workspace",
    "resolve_existing_file_under_workspace",
    "resolve_path_under_workspace",
    "resolve_path_under_workspace_or_tool_error",
    "suggest_sibling_directories_for_missing_path",
)

_MAX_DIRECTORY_SUGGESTIONS: int = 5
_MIN_DIRECTORY_SUGGESTION_SCORE: float = 0.55


def resolve_path_under_workspace(
    path_value: str,
    *,
    workspace_path: str,
    description: str,
) -> str:
    return resolve_rooted_path(
        path_value,
        base_path=workspace_path,
        description=description,
        error_cls=ValidationError,
    )


def resolve_path_under_workspace_or_tool_error(
    path_value: str,
    *,
    workspace_path: str,
    description: str,
) -> str:
    try:
        return resolve_path_under_workspace(
            path_value,
            workspace_path=workspace_path,
            description=description,
        )
    except ValidationError as exception:
        raise MCPToolError(-32602, str(exception)) from exception


def resolve_existing_dir_under_workspace(
    dir_path: str,
    *,
    workspace_path: str,
    description: str,
) -> str:
    try:
        resolved = resolve_path_under_workspace(
            dir_path,
            workspace_path=workspace_path,
            description=description,
        )
    except ValidationError as exception:
        raise MCPToolError(-32602, str(exception)) from exception
    if os.path.isdir(resolved):
        return resolved
    raise MCPToolError(
        -32602,
        build_missing_directory_error_message(
            dir_path,
            workspace_path=workspace_path,
            description=description,
        ),
    )


def resolve_existing_file_under_workspace(
    file_path: str,
    *,
    workspace_path: str,
    description: str,
) -> str:
    return resolve_rooted_existing_file(
        file_path,
        base_path=workspace_path,
        description=description,
        error_cls=ValidationError,
    )


def _normalize_directory_name(value: str) -> str:
    return value.replace("-", "").replace("_", "").lower()


def _collect_directory_names(parent_dir: str) -> list[str]:
    try:
        with os.scandir(parent_dir) as entries:
            return sorted(entry.name for entry in entries if entry.is_dir(follow_symlinks=False))
    except OSError:
        return []


def _score_directory_name(target_name: str, candidate_name: str) -> float:
    normalized_target = _normalize_directory_name(target_name)
    normalized_candidate = _normalize_directory_name(candidate_name)
    if not normalized_target or not normalized_candidate:
        return 0.0
    if normalized_target == normalized_candidate:
        return 1.0
    return difflib.SequenceMatcher(a=normalized_target, b=normalized_candidate).ratio()


def suggest_sibling_directories_for_missing_path(
    missing_directory_path: str,
    *,
    workspace_path: str,
    description: str,
) -> list[str]:
    target_name = os.path.basename(missing_directory_path.rstrip(os.sep))
    if not target_name:
        return []
    parent_dir = os.path.dirname(missing_directory_path)
    try:
        resolved_parent = ensure_path_within_base(
            workspace_path,
            parent_dir,
            description=description,
            error_cls=ValidationError,
        )
    except ValidationError:
        return []
    if not os.path.isdir(resolved_parent):
        return []
    candidate_names = _collect_directory_names(resolved_parent)
    scored_candidates: list[tuple[float, str]] = []
    for candidate_name in candidate_names:
        score = _score_directory_name(target_name, candidate_name)
        if score >= _MIN_DIRECTORY_SUGGESTION_SCORE:
            scored_candidates.append((score, candidate_name))
    scored_candidates.sort(key=lambda item: (-item[0], item[1]))
    return [
        os.path.join(resolved_parent, candidate_name)
        for _, candidate_name in scored_candidates[:_MAX_DIRECTORY_SUGGESTIONS]
    ]


def build_missing_directory_error_message(
    dir_path: str,
    *,
    workspace_path: str,
    description: str,
) -> str:
    resolved_candidate = resolve_rooted_candidate_path(dir_path, base_path=workspace_path)
    base_directory = workspace_path
    message = (
        f"{description} is not a directory: {dir_path}. "
        f"Resolved path: {resolved_candidate}. "
        f"Base directory: {base_directory}."
    )
    suggestions = suggest_sibling_directories_for_missing_path(
        resolved_candidate,
        workspace_path=workspace_path,
        description=description,
    )
    if suggestions:
        rendered_suggestions = ", ".join(f"'{candidate}'" for candidate in suggestions)
        message = f"{message} Did you mean: {rendered_suggestions}?"
    return message
