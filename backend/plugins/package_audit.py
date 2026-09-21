"""SoAI - Canonical plugin ZIP package audits [backend/plugins/package_audit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.errors.exceptions import NotFoundError, StateError, ValidationError
from core.filesystem.open_files import open_regular_binary_no_symlink
from core.logging.trace import get_logger
from core.plugins.logo_contract import PluginLogoResult
from core.plugins.logo_images import sanitize_plugin_logo
from core.types.json import is_str_list
from core.types.json_value import copy_json_dict
from plugins.hash_blocklist import (
    build_blocked_plugin_hash_error,
    get_blocked_plugin_hash_compatibility,
)
from plugins.manifest.ast_contracts import (
    eval_required_literal,
    extract_class_assignments,
    get_plugin_class_node,
)
from plugins.manifest.class_field_contract import PLUGIN_FIELD_PACKAGE_DEPENDENCIES
from plugins.package_content import PluginPackageContent
from plugins.package_dependency_validation import ensure_declared_package_dependencies
from plugins.package_inspection import (
    PluginPackageSnapshot,
    inspect_plugin_package_stream,
)
from plugins.path_safety import get_plugin_file_path
from plugins.security import ensure_import_tree_has_no_forbidden_imports

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginDownloadManagerProtocol,
    )

__all__ = (
    "PluginPackageAudit",
    "audit_plugin_package",
    "inspect_open_plugin_package",
    "inspect_plugin_package",
)

LOGGER_NAME = "SoAI.plugins.package_audit"


@dataclass(frozen=True, slots=True)
class PluginPackageAudit:
    plugin_name: str
    archive_path: str
    content: PluginPackageContent
    imports_validated: bool
    parameter_schema: JSONDict | None
    logo: PluginLogoResult = field(default_factory=lambda: PluginLogoResult(status="absent"))


def _open_plugin_snapshot(plugin_name: str, archive_path: str) -> PluginPackageSnapshot:
    try:
        file_handle = open_regular_binary_no_symlink(
            archive_path,
            not_found_message="Plugin package was not found.",
            symlink_message="Plugin package is a symbolic link.",
            open_message="Plugin package could not be opened.",
            inspect_message="Plugin package could not be inspected.",
            regular_file_message="Plugin package is not a regular file.",
        )
    except ValidationError as exception:
        if not os.path.lexists(archive_path):
            raise NotFoundError(
                f"Plugin package not found for '{plugin_name}' at {archive_path}",
            ) from exception
        raise StateError(f"Could not open plugin package for '{plugin_name}'.") from exception
    with file_handle:
        return inspect_plugin_package_stream(plugin_name, file_handle)


def _audit_snapshot(
    plugin_name: str,
    archive_path: str,
    snapshot: PluginPackageSnapshot,
    *,
    enforce_import_scan: bool,
    enforce_hash_policy: bool,
) -> PluginPackageAudit:
    if (
        enforce_hash_policy
        and get_blocked_plugin_hash_compatibility(snapshot.content.archive_hash) is not None
    ):
        raise build_blocked_plugin_hash_error(plugin_name, snapshot.content.archive_hash)
    class_node = get_plugin_class_node(snapshot.content.entrypoint.parsed_source)
    assignments = extract_class_assignments(class_node)
    packages = eval_required_literal(assignments, PLUGIN_FIELD_PACKAGE_DEPENDENCIES)
    if not is_str_list(packages):
        raise ValidationError("Plugin PACKAGE_DEPENDENCIES must be a list of strings.")
    package_names = list(packages)
    if enforce_import_scan:
        for python_member in snapshot.content.python_members:
            ensure_import_tree_has_no_forbidden_imports(
                plugin_name,
                python_member.parsed_source,
            )
            ensure_declared_package_dependencies(
                plugin_name,
                python_member.parsed_source,
                package_names,
            )
    logo = sanitize_plugin_logo(snapshot.logo_source)
    if logo.status == "invalid":
        get_logger(LOGGER_NAME).warning(
            "Plugin '%s' optional artwork rejected: %s",
            plugin_name,
            logo.reason,
        )
    return PluginPackageAudit(
        plugin_name=plugin_name,
        archive_path=archive_path,
        content=snapshot.content,
        imports_validated=enforce_import_scan,
        logo=logo,
        parameter_schema=(
            copy_json_dict(snapshot.parameter_schema)
            if snapshot.parameter_schema is not None
            else None
        ),
    )


async def audit_plugin_package(
    manager: PluginDownloadManagerProtocol,
    plugin_name: str,
    *,
    file_path_override: str | None = None,
    enforce_import_scan: bool = True,
    enforce_hash_policy: bool = True,
) -> PluginPackageAudit:
    archive_path = file_path_override or get_plugin_file_path(manager, plugin_name)
    return await asyncio.to_thread(
        inspect_plugin_package,
        plugin_name,
        archive_path,
        enforce_import_scan=enforce_import_scan,
        enforce_hash_policy=enforce_hash_policy,
    )


def inspect_plugin_package(
    plugin_name: str,
    archive_path: str,
    *,
    enforce_import_scan: bool = True,
    enforce_hash_policy: bool = True,
) -> PluginPackageAudit:
    return _audit_snapshot(
        plugin_name,
        archive_path,
        _open_plugin_snapshot(plugin_name, archive_path),
        enforce_import_scan=enforce_import_scan,
        enforce_hash_policy=enforce_hash_policy,
    )


def inspect_open_plugin_package(
    plugin_name: str,
    archive_path: str,
    file_handle: io.BufferedIOBase | io.RawIOBase,
    *,
    enforce_import_scan: bool = True,
    enforce_hash_policy: bool = True,
) -> PluginPackageAudit:
    return _audit_snapshot(
        plugin_name,
        archive_path,
        inspect_plugin_package_stream(plugin_name, file_handle),
        enforce_import_scan=enforce_import_scan,
        enforce_hash_policy=enforce_hash_policy,
    )
