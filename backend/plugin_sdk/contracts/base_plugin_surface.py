"""SoAI - BasePlugin surface methods [backend/plugin_sdk/contracts/base_plugin_surface.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.plugins.base_plugin_surface import (
    get_default_configuration_template,
    get_default_log_path,
    get_models_directory,
    open_log_file_for_command,
    supports_modality,
)

__all__ = (
    "get_default_configuration_template",
    "get_default_log_path",
    "get_models_directory",
    "open_log_file_for_command",
    "supports_modality",
)
