"""SoAI - Workspace virtual path conversion helpers [backend/core/files/workspace_virtual_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.files.workspace_descriptor import (
    normalize_workspace_virtual_path_parts,
    stat_workspace_entry,
)

__all__ = (
    "conversation_virtual_path_from_real_path",
    "conversation_virtual_path_from_user_virtual_path",
    "real_path_from_workspace_virtual_path",
    "user_virtual_path_from_conversation_virtual_path",
)


def _raise(error_cls: type[Exception], message: str) -> None:
    raise error_cls(message)


def conversation_virtual_path_from_real_path(
    workspace_root: str,
    real_path: str,
    *,
    error_cls: type[Exception] = ValueError,
) -> str:
    root = os.path.realpath(os.path.abspath(workspace_root))
    target = os.path.realpath(os.path.abspath(real_path))
    try:
        relative = os.path.relpath(target, root)
    except ValueError as exception:
        raise error_cls("SoAI path target is outside the conversation workspace.") from exception
    if relative == "." or relative.startswith(f"..{os.sep}") or relative == "..":
        _raise(error_cls, "SoAI path target is outside the conversation workspace.")
    parts = [part for part in relative.split(os.sep) if part and part != "."]
    if not parts or any(part == ".." for part in parts):
        _raise(error_cls, "SoAI path target cannot be the workspace root.")
    return f"/{'/'.join(parts)}"


def conversation_virtual_path_from_user_virtual_path(
    *,
    user_root: str,
    effective_workspace_root: str,
    user_virtual_path: str,
    error_cls: type[Exception] = ValueError,
) -> str:
    user_parts = normalize_workspace_virtual_path_parts(
        user_root,
        user_virtual_path,
        error_cls=error_cls,
    )
    stat_workspace_entry(user_root, user_virtual_path, error_cls=error_cls)
    user_root_abs = os.path.realpath(os.path.abspath(user_root))
    effective_root_abs = os.path.realpath(os.path.abspath(effective_workspace_root))
    target_abs = os.path.abspath(os.path.join(user_root_abs, *user_parts))
    try:
        relative = os.path.relpath(target_abs, effective_root_abs)
    except ValueError as exception:
        raise error_cls("SoAI path target is outside the conversation workspace.") from exception
    if relative == "." or relative.startswith(f"..{os.sep}") or relative == "..":
        _raise(error_cls, "SoAI path target is outside the conversation workspace.")
    parts = [part for part in relative.split(os.sep) if part and part != "."]
    if not parts or any(part == ".." for part in parts):
        _raise(error_cls, "SoAI path target cannot be the workspace root.")
    conversation_virtual_path = f"/{'/'.join(parts)}"
    stat_workspace_entry(effective_root_abs, conversation_virtual_path, error_cls=error_cls)
    return conversation_virtual_path


def real_path_from_workspace_virtual_path(
    workspace_root: str,
    conversation_virtual_path: str,
    *,
    error_cls: type[Exception] = ValueError,
) -> str:
    parts = normalize_workspace_virtual_path_parts(
        workspace_root,
        conversation_virtual_path,
        error_cls=error_cls,
    )
    stat_workspace_entry(workspace_root, conversation_virtual_path, error_cls=error_cls)
    return os.path.join(os.path.realpath(os.path.abspath(workspace_root)), *parts)


def user_virtual_path_from_conversation_virtual_path(
    *,
    user_root: str,
    effective_workspace_root: str,
    conversation_virtual_path: str,
    error_cls: type[Exception] = ValueError,
) -> str:
    parts = normalize_workspace_virtual_path_parts(
        effective_workspace_root,
        conversation_virtual_path,
        error_cls=error_cls,
    )
    stat_workspace_entry(effective_workspace_root, conversation_virtual_path, error_cls=error_cls)
    user_root_abs = os.path.realpath(os.path.abspath(user_root))
    effective_root_abs = os.path.realpath(os.path.abspath(effective_workspace_root))
    target_abs = os.path.abspath(os.path.join(effective_root_abs, *parts))
    try:
        relative = os.path.relpath(target_abs, user_root_abs)
    except ValueError as exception:
        raise error_cls(
            "SoAI path target is not representable in the user workspace.",
        ) from exception
    if relative == "." or relative.startswith(f"..{os.sep}") or relative == "..":
        _raise(error_cls, "SoAI path target is not representable in the user workspace.")
    user_virtual_path = f"/{relative.replace(os.sep, '/')}"
    stat_workspace_entry(user_root_abs, user_virtual_path, error_cls=error_cls)
    return user_virtual_path
