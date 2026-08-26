"""SoAI - Project root file access for API runtime [backend/features/api/runtime/project_root_files.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import NotFoundError, ValidationError
from core.filesystem.open_files import open_text
from core.meta.paths import get_project_root

__all__ = (
    "read_text_file_from_project_root",
    "resolve_project_root_dir",
)


def resolve_project_root_dir() -> str:
    return get_project_root()


def read_text_file_from_project_root(
    candidate_files: tuple[str, ...],
) -> tuple[str, str]:
    if not candidate_files:
        raise ValidationError("candidate_files must not be empty.")
    project_root = resolve_project_root_dir()
    for filename in candidate_files:
        normalized = filename.strip()
        if not normalized:
            continue
        file_path = os.path.join(project_root, normalized)
        if not os.path.exists(file_path):
            continue
        with open_text(file_path, encoding="utf-8") as file_handle:
            return (normalized, file_handle.read())
    raise NotFoundError(f"File not found in project root. Tried: {', '.join(candidate_files)}")
