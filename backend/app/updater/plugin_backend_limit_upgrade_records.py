"""SoAI - Offline plugin limit preparation and result records [backend/app/updater/plugin_backend_limit_upgrade_records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import stat
from dataclasses import dataclass

from ruamel.yaml.comments import CommentedMap

from core.files.file_identity import FileIdentity
from plugins.package_inspection import PluginPackageSnapshot

__all__ = (
    "DeclaredPluginBackendLimit",
    "PreparedPluginBackendLimit",
    "PluginBackendLimitRefreshResult",
)


@dataclass(frozen=True, slots=True)
class DeclaredPluginBackendLimit:
    package_path: str
    package_identity: FileIdentity
    snapshot: PluginPackageSnapshot
    limit: str


@dataclass(frozen=True, slots=True)
class PreparedPluginBackendLimit:
    config_path: str
    original: bytes
    identity: FileIdentity
    permissions: int
    mapping: CommentedMap
    proposed: str

    def matches_original(self, contents: bytes, identity: FileIdentity) -> bool:
        return contents == self.original and stat.S_IMODE(identity.mode) == self.permissions


@dataclass(frozen=True, slots=True)
class PluginBackendLimitRefreshResult:
    changed_paths: tuple[str, ...]
    retained_originals: str | None
