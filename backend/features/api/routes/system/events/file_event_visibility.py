"""SoAI - File explorer WebSocket event visibility [backend/features/api/routes/system/events/file_event_visibility.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.events.types_file_explorer import FileSystemChangedEvent
from core.files.path_policy import ensure_path_within_base, is_path_overlap_with_base
from core.files.workspace_path import resolve_workspace_real_path

if TYPE_CHECKING:
    from collections.abc import Mapping

    from core.files.protocols import FilesPathResolverProtocol
    from core.types.json import JSONValue

__all__ = ("file_system_event_visible_to_user",)


def file_system_event_visible_to_user(
    event: FileSystemChangedEvent,
    *,
    current_user: Mapping[str, JSONValue],
    files: FilesPathResolverProtocol,
) -> bool:
    event_root = _normalize_absolute_path(event.workspace_root_path)
    workspace_path = current_user.get("workspace_path")
    if not isinstance(workspace_path, str):
        return False
    try:
        viewer_root = resolve_workspace_real_path(files, workspace_path)
    except (StateError, ValidationError):
        return False
    if event_root is None:
        return False
    for event_path in _iter_file_system_event_paths(event, event_root):
        if is_path_overlap_with_base(event_path, viewer_root):
            return True
    return False


def _normalize_absolute_path(value: str) -> str | None:
    stripped = value.strip()
    if not stripped or "\x00" in stripped:
        return None
    return os.path.realpath(os.path.abspath(stripped))


def _iter_file_system_event_paths(
    event: FileSystemChangedEvent,
    event_root: str,
) -> tuple[str, ...]:
    paths: list[str] = []
    for virtual_path in (event.virtual_path, event.destination_virtual_path):
        if virtual_path is None:
            continue
        resolved = _resolve_file_system_event_path(event_root, virtual_path)
        if resolved is not None:
            paths.append(resolved)
    return tuple(paths)


def _resolve_file_system_event_path(event_root: str, virtual_path: str) -> str | None:
    if not isinstance(virtual_path, str) or "\x00" in virtual_path:
        return None
    stripped = virtual_path.strip()
    if not stripped or stripped == "/":
        return event_root
    relative_path = stripped.lstrip("/\\")
    if not relative_path:
        return event_root
    candidate_path = os.path.join(event_root, relative_path)
    try:
        return ensure_path_within_base(
            event_root,
            candidate_path,
            description="File explorer event path",
            error_cls=ValidationError,
        )
    except ValidationError:
        return None
