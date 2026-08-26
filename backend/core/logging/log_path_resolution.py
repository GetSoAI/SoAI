"""SoAI - Log path resolution and validation helpers [backend/core/logging/log_path_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.files.path_policy import is_path_inside_directory

__all__ = ("resolve_full_log_path",)


def resolve_full_log_path(
    config: ConfigProtocol,
    *,
    filename_key: str,
    default_filename: str,
) -> str:
    base_path_value = config.get_str("SYSTEM.PATHS.BASE")
    base_candidate = base_path_value.strip() if isinstance(base_path_value, str) else ""
    if not base_candidate:
        raise ValidationError("SYSTEM.PATHS.BASE must be a non-empty string.")
    base_path = os.path.abspath(base_candidate)
    log_path_value = config.get_str("OBSERVABILITY.LOGGING.LOGS_PATH")
    log_candidate = log_path_value.strip() if isinstance(log_path_value, str) else ""
    if not log_candidate:
        raise ValidationError("OBSERVABILITY.LOGGING.LOGS_PATH must be a non-empty string.")
    log_path = log_candidate
    if not os.path.isabs(log_path):
        log_path = os.path.join(base_path, log_path)
    log_path = os.path.abspath(log_path)
    forbidden_path = os.path.join(base_path, "logs")
    if is_path_inside_directory(forbidden_path, log_path):
        raise ValidationError(
            "OBSERVABILITY.LOGGING.LOGS_PATH must not target the base path logs directory.",
            details={"logs_path": log_path},
        )
    filename_value = config.get_str(filename_key)
    filename_candidate = filename_value.strip() if isinstance(filename_value, str) else ""
    filename = default_filename if not filename_candidate else filename_candidate
    if not filename:
        raise ValidationError(f"{filename_key} must not resolve to an empty filename.")
    full_path = (
        os.path.abspath(os.path.join(log_path, filename))
        if not os.path.isabs(filename)
        else os.path.abspath(filename)
    )
    if is_path_inside_directory(forbidden_path, full_path):
        raise ValidationError(
            "OBSERVABILITY.LOGGING log files must not be stored under the base path logs directory.",
            details={"log_file": full_path},
        )
    return full_path
