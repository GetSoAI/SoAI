"""SoAI - Manual install path payload resolution [backend/core/manual_install_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TypedDict

from core.config.protocols import ConfigProtocol
from core.files.protocols import FilesPathResolverProtocol

__all__ = ("ManualInstallPathPayload", "build_manual_install_path_payload")


class ManualInstallPathPayload(TypedDict):
    resource_type: str
    configured_path: str
    resolved_path: str


def build_manual_install_path_payload(
    *,
    config: ConfigProtocol,
    files: FilesPathResolverProtocol,
    resource_type: str,
    config_key: str,
) -> ManualInstallPathPayload:
    configured_path = config.require_str(config_key)
    resolved_path = files.resolve_path(configured_path)
    return {
        "resource_type": resource_type,
        "configured_path": configured_path,
        "resolved_path": resolved_path,
    }
