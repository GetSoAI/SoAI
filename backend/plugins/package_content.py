"""SoAI - Inspected plugin package content records [backend/plugins/package_content.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ast
from dataclasses import dataclass

from core.archives.zip_plan import ValidatedZipPlan

__all__ = (
    "PluginPackageContent",
    "PluginPackageMemberDigest",
    "PluginPythonMemberAudit",
)


@dataclass(frozen=True, slots=True)
class PluginPythonMemberAudit:
    logical_path: str
    source_text: str
    parsed_source: ast.Module
    file_size: int


@dataclass(frozen=True, slots=True)
class PluginPackageMemberDigest:
    logical_path: str
    destination_path: str
    file_size: int
    sha256_hex: str


@dataclass(frozen=True, slots=True)
class PluginPackageContent:
    archive_hash: str
    zip_plan: ValidatedZipPlan
    expanded_size: int
    member_digests: tuple[PluginPackageMemberDigest, ...]
    entrypoint: PluginPythonMemberAudit
    python_members: tuple[PluginPythonMemberAudit, ...]
