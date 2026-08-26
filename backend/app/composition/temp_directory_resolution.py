"""SoAI - SYSTEM.PATHS.TEMP resolution for orchestrator assembly [backend/app/composition/temp_directory_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.config.protocols import ConfigProtocol

__all__ = ("resolve_temp_directory",)


def resolve_temp_directory(config: ConfigProtocol) -> str | None:
    temp_directory_value = config.get("SYSTEM.PATHS.TEMP")
    if isinstance(temp_directory_value, str) and temp_directory_value.strip():
        return temp_directory_value
    return None
