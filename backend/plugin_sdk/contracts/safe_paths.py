"""SoAI - Plugin SDK safe path helpers [backend/plugin_sdk/contracts/safe_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys

from core.errors.exceptions import ValidationError
from core.files.path_policy import safe_join_relative_under_base

__all__ = ("resolve_plugin_backend_root", "safe_join_under_base")


def resolve_plugin_backend_root(configured_path: str) -> str:
    if not isinstance(configured_path, str) or not configured_path.strip():
        raise ValidationError("configured_path must be a non-empty string.")
    normalized_path = os.path.abspath(configured_path.strip())
    if sys.platform != "win32":
        return normalized_path
    program_data = os.environ.get("ProgramData", "").strip()
    if not program_data:
        raise ValidationError("ProgramData is required for managed Windows plugin backends.")
    backend_name = os.path.basename(os.path.normpath(normalized_path))
    resolved_path = safe_join_relative_under_base(
        base_path=program_data,
        relative_path=os.path.join("SoAI", "backends", backend_name),
        description="managed plugin backend path",
        error_cls=ValidationError,
        base_error_message="ProgramData must be a non-empty path.",
        relative_error_message="Plugin backend name must be non-empty.",
        absolute_error_message="Plugin backend name must be relative.",
    )
    if " " in resolved_path:
        raise ValidationError("The managed Windows plugin backend path must not contain spaces.")
    return resolved_path


def safe_join_under_base(*, base_dir: str, relative_path: str, description: str) -> str:
    return safe_join_relative_under_base(
        base_path=base_dir,
        relative_path=relative_path,
        description=description,
        error_cls=ValidationError,
        base_error_message="base_dir must be a non-empty string.",
        relative_error_message="relative_path must be a non-empty string.",
        absolute_error_message="Absolute paths are not permitted.",
    )
