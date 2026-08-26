"""SoAI - Plugin log file source resolution [backend/core/logging/plugin_log_files.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import re

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.files.path_policy import ensure_path_within_base
from core.meta.paths import join_data_abs

__all__ = (
    "list_plugin_log_sources",
    "resolve_plugin_log_file",
)

_PLUGIN_SOURCE_PATTERN_TEXT: str = r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"


def _resolve_plugin_logs_directory(config: ConfigProtocol) -> str:
    path_value = config.get_str("PLUGINS.PATHS.PLUGIN_LOGS")
    candidate = path_value.strip() if isinstance(path_value, str) else ""
    if not candidate:
        raise ValidationError("PLUGINS.PATHS.PLUGIN_LOGS must be a non-empty string.")
    if os.path.isabs(candidate):
        return os.path.abspath(candidate)
    base_value = config.get_str("SYSTEM.PATHS.BASE")
    base_path = base_value.strip() if isinstance(base_value, str) else ""
    if not base_path:
        raise ValidationError("SYSTEM.PATHS.BASE must be a non-empty string.")
    return join_data_abs(base_path, candidate)


def _validate_plugin_source_name(source: str) -> str:
    normalized = source.strip()
    if not normalized:
        raise ValidationError("Plugin log source must be a non-empty string.")
    if re.fullmatch(_PLUGIN_SOURCE_PATTERN_TEXT, normalized) is None:
        raise ValidationError("Plugin log source contains invalid characters.")
    return normalized


def resolve_plugin_log_file(config: ConfigProtocol, source: str) -> str | None:
    normalized = _validate_plugin_source_name(source)
    directory_path = _resolve_plugin_logs_directory(config)
    lexical_candidate_path = os.path.abspath(os.path.join(directory_path, f"{normalized}.log"))
    if os.path.islink(lexical_candidate_path):
        raise ValidationError("Plugin log source must not be a symbolic link.")
    candidate_path = ensure_path_within_base(
        directory_path,
        lexical_candidate_path,
        description="Plugin log source path",
        error_cls=ValidationError,
    )
    if not os.path.isfile(candidate_path):
        return None
    return candidate_path


def list_plugin_log_sources(config: ConfigProtocol) -> list[str]:
    directory_path = _resolve_plugin_logs_directory(config)
    if not os.path.isdir(directory_path):
        return []
    sources: list[str] = []
    for filename in os.listdir(directory_path):
        if not filename.endswith(".log"):
            continue
        source = filename[:-4]
        resolved = resolve_plugin_log_file(config, source)
        if resolved is not None:
            sources.append(source)
    return sorted(set(sources))
