"""SoAI - Plugin environment path resolution [backend/plugins/environments/paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import ValidationError
from core.files.path_policy import ensure_path_within_base
from plugins.identity import require_plugin_identifier

__all__ = ("resolve_plugin_environment_path",)


def resolve_plugin_environment_path(plugin_venvs_root: str, plugin_name: str) -> str:
    require_plugin_identifier(plugin_name, invalid_message=f"Invalid plugin name '{plugin_name}'.")
    root_value = str(plugin_venvs_root or "").strip()
    if not root_value:
        raise ValidationError("Plugin env root is not configured.")
    root = os.path.realpath(os.path.abspath(root_value))
    candidate = os.path.realpath(os.path.join(root, plugin_name))
    return ensure_path_within_base(
        root,
        candidate,
        description="Plugin environment path",
        error_cls=ValidationError,
    )
