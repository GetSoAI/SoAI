"""SoAI - Configured storage on network or unmapped Windows drives [backend/core/config/remote_storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.layout import BASE_DOTTED_KEYS, STATE_DOTTED_KEYS
from core.filesystem.windows_remote_paths import is_windows_remote_or_unmapped_path

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol

__all__ = ("find_remote_storage_settings",)


def find_remote_storage_settings(config: ConfigProtocol) -> tuple[str, ...]:
    remote_settings: list[str] = []
    for key in sorted(STATE_DOTTED_KEYS | BASE_DOTTED_KEYS):
        value = config.get_str(key)
        if value and is_windows_remote_or_unmapped_path(value):
            remote_settings.append(key)
    return tuple(remote_settings)
