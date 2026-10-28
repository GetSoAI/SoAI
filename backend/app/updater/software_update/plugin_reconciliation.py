"""SoAI - Bundled update package reconciliation [backend/app/updater/software_update/plugin_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

from packaging.specifiers import InvalidSpecifier, SpecifierSet

from app.backup.backup_removal import sync_remove_tree_no_symlinks
from app.updater.disk_space import require_disk_space_for_update
from core.bootstrap.install_payload_transaction import copy_install_entry, install_entry_copy_size
from core.errors.exceptions import ValidationError
from core.files.file_identity import FileIdentity
from core.files.staged_transfer import compute_file_sha256
from core.hardware.reservation_claims import claim_reserved_write
from core.meta.versioning import NormalizedVersion, parse_semantic_version
from core.plugins.builtin_names import BUILTIN_PLUGIN_NAMES
from core.plugins.file_suffixes import PLUGIN_CONFIG_FILE_SUFFIX, PLUGIN_FILE_SUFFIX
from plugins.manifest.ast_contracts import (
    eval_required_literal,
    extract_class_assignments,
    get_plugin_class_node,
)
from plugins.manifest.class_field_contract import (
    PLUGIN_FIELD_AUTHOR_SOAIPLUGIN,
    PLUGIN_FIELD_NAME,
    PLUGIN_FIELD_REQUIRED_SOAI_VERSION,
    PLUGIN_FIELD_VERSION_SOAIPLUGIN,
    PLUGIN_FIELD_WEBSITE_SOAIPLUGIN,
)
from plugins.manifest.normalized_fields import (
    normalize_required_non_empty_string_field,
    normalize_required_string_field,
)
from plugins.package_inspection import inspect_plugin_package_file

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = (
    "PluginReconciliationPlan",
    "plan_plugin_reconciliation",
    "reconcile_staged_plugins",
    "stage_configured_plugins",
)


@dataclass(frozen=True, slots=True)
class UpdatePluginIdentity:
    name: str
    author: str
    website: str
    version: NormalizedVersion
    sha256: str
    file_identity: FileIdentity


@dataclass(frozen=True, slots=True)
class PluginReconciliationPlan:
    preservation_names: tuple[str, ...]
    installed_packages: dict[str, UpdatePluginIdentity]
    required_bytes: int
    staged_packages: dict[str, UpdatePluginIdentity]
    deleted_builtin_packages: tuple[str, ...] = ()


def _read_compatible_package(path: str, target_version: str) -> UpdatePluginIdentity:
    snapshot, identity = inspect_plugin_package_file(path)
    assignments = extract_class_assignments(
        get_plugin_class_node(snapshot.content.entrypoint.parsed_source)
    )
    required_version = normalize_required_non_empty_string_field(
        eval_required_literal(assignments, PLUGIN_FIELD_REQUIRED_SOAI_VERSION),
        field_name=PLUGIN_FIELD_REQUIRED_SOAI_VERSION,
    )
    try:
        compatible = SpecifierSet(required_version).contains(
            parse_semantic_version(target_version),
            prereleases=True,
        )
    except InvalidSpecifier as exception:
        raise ValidationError(
            f"Plugin {os.path.basename(path)} declares an invalid SoAI compatibility range."
        ) from exception
    if not compatible:
        raise ValidationError(
            f"Plugin {os.path.basename(path)} requires SoAI {required_version}; install a compatible package before updating to {target_version}."
        )
    return UpdatePluginIdentity(
        name=normalize_required_non_empty_string_field(
            eval_required_literal(assignments, PLUGIN_FIELD_NAME), field_name=PLUGIN_FIELD_NAME
        ),
        author=normalize_required_string_field(
            eval_required_literal(assignments, PLUGIN_FIELD_AUTHOR_SOAIPLUGIN),
            field_name=PLUGIN_FIELD_AUTHOR_SOAIPLUGIN,
        ),
        website=normalize_required_string_field(
            eval_required_literal(assignments, PLUGIN_FIELD_WEBSITE_SOAIPLUGIN),
            field_name=PLUGIN_FIELD_WEBSITE_SOAIPLUGIN,
        ),
        version=parse_semantic_version(
            normalize_required_non_empty_string_field(
                eval_required_literal(assignments, PLUGIN_FIELD_VERSION_SOAIPLUGIN),
                field_name=PLUGIN_FIELD_VERSION_SOAIPLUGIN,
            )
        ),
        sha256=snapshot.content.archive_hash,
        file_identity=identity,
    )


def plan_plugin_reconciliation(
    *,
    installed_plugins: str,
    staged_plugins: str,
    target_version: str,
    existing_installation: bool = True,
) -> PluginReconciliationPlan:
    if os.path.islink(staged_plugins) or not os.path.isdir(staged_plugins):
        raise ValidationError("Bundled plugins must be a regular directory before updating.")
    target_packages = {
        name: _read_compatible_package(os.path.join(staged_plugins, name), target_version)
        for name in os.listdir(staged_plugins)
        if name.endswith(PLUGIN_FILE_SUFFIX)
    }
    if not os.path.lexists(installed_plugins):
        return PluginReconciliationPlan(
            (),
            {},
            0,
            target_packages,
            tuple(
                name
                for name in target_packages
                if existing_installation
                and name.removesuffix(PLUGIN_FILE_SUFFIX) in BUILTIN_PLUGIN_NAMES
            ),
        )
    if os.path.islink(installed_plugins) or not os.path.isdir(installed_plugins):
        raise ValidationError("Installed plugins must be a directory before updating.")
    installed_names = os.listdir(installed_plugins)
    preservation_names: list[str] = []
    installed_packages: dict[str, UpdatePluginIdentity] = {}
    for name in installed_names:
        if name.endswith(PLUGIN_FILE_SUFFIX):
            installed_packages[name] = _read_compatible_package(
                os.path.join(installed_plugins, name),
                target_version,
            )
    for target_name, target_package in target_packages.items():
        normalized_target = unicodedata.normalize("NFC", target_name).casefold()
        collisions = [
            name
            for name in installed_names
            if unicodedata.normalize("NFC", name).casefold() == normalized_target
        ]
        if not collisions:
            continue
        if collisions != [target_name] or target_name not in installed_packages:
            raise ValidationError(
                f"Bundled plugin {target_name} conflicts with installed content; resolve the name collision before updating."
            )
        installed_package = installed_packages[target_name]
        if (
            installed_package.name != target_package.name
            or installed_package.author != target_package.author
        ):
            raise ValidationError(
                f"Bundled plugin {target_name} has an ambiguous installed identity; preserve or rename the custom package before updating."
            )
        if installed_package.version == target_package.version:
            if installed_package.sha256 != target_package.sha256:
                raise ValidationError(
                    f"Plugin {target_name} has conflicting bytes at the same package version; resolve the package conflict before updating."
                )
            preservation_names.append(target_name)
        elif installed_package.version > target_package.version:
            preservation_names.append(target_name)
    preservation_names.extend(name for name in installed_names if name not in target_packages)
    required_bytes = sum(
        install_entry_copy_size(os.path.join(installed_plugins, name))
        for name in preservation_names
    )
    deleted = tuple(
        name
        for name in target_packages
        if existing_installation
        and name.removesuffix(PLUGIN_FILE_SUFFIX) in BUILTIN_PLUGIN_NAMES
        and name not in installed_packages
    )
    return PluginReconciliationPlan(
        tuple(preservation_names), installed_packages, required_bytes, target_packages, deleted
    )


def _require_packages_unchanged(
    directory: str, expected: dict[str, UpdatePluginIdentity], target_version: str
) -> None:
    names: set[str] = (
        {name for name in os.listdir(directory) if name.endswith(PLUGIN_FILE_SUFFIX)}
        if os.path.lexists(directory)
        else set()
    )
    if names != set(expected):
        raise ValidationError("Plugin selection changed during update preparation.")
    for name, previous in expected.items():
        current = _read_compatible_package(os.path.join(directory, name), target_version)
        if (
            current.sha256 != previous.sha256
            or not previous.file_identity.matches_descriptor_snapshot(current.file_identity)
        ):
            raise ValidationError("Plugin package changed during update preparation.")


def reconcile_staged_plugins(
    *,
    installed_plugins: str,
    staged_plugins: str,
    target_version: str,
    reservation_provider: StorageManagerProtocol,
    existing_installation: bool = True,
    preserve_configurations: bool = True,
    associated_configurations_only: bool = False,
) -> None:
    plan = plan_plugin_reconciliation(
        installed_plugins=installed_plugins,
        staged_plugins=staged_plugins,
        target_version=target_version,
        existing_installation=existing_installation,
    )
    associated_configurations = {
        name.removesuffix(PLUGIN_FILE_SUFFIX) + PLUGIN_CONFIG_FILE_SUFFIX
        for name in plan.installed_packages
    }
    with reservation_provider.reserve_disk_space(
        path=staged_plugins,
        required_bytes=plan.required_bytes,
        operation="application_updater.preserve_plugins",
        details={"package_count": len(plan.preservation_names)},
    ) as reservation:
        with claim_reserved_write(reservation, size_bytes=plan.required_bytes):
            _require_packages_unchanged(installed_plugins, plan.installed_packages, target_version)
            _require_packages_unchanged(staged_plugins, plan.staged_packages, target_version)
            for name in plan.preservation_names:
                if not preserve_configurations and name not in plan.installed_packages:
                    continue
                if associated_configurations_only and name not in (
                    plan.installed_packages.keys() | associated_configurations
                ):
                    continue
                target = os.path.join(staged_plugins, name)
                inspected_package = plan.installed_packages.get(name)
                if (
                    inspected_package is not None
                    and os.path.lexists(target)
                    and compute_file_sha256(target).sha256_hex == inspected_package.sha256
                ):
                    continue
                if os.path.lexists(target):
                    sync_remove_tree_no_symlinks(target)
                copy_install_entry(os.path.join(installed_plugins, name), staged_plugins)
                inspected_package = plan.installed_packages.get(name)
                if (
                    inspected_package is not None
                    and compute_file_sha256(target).sha256_hex != inspected_package.sha256
                ):
                    raise ValidationError(
                        f"Plugin {name} changed during update preparation; retry after plugin changes finish."
                    )
            for name in plan.deleted_builtin_packages:
                os.unlink(os.path.join(staged_plugins, name))


def stage_configured_plugins(
    *,
    installed_plugins: str,
    bundled_plugins: str,
    staging_parent: str,
    target_version: str,
    reservation_provider: StorageManagerProtocol,
) -> str:
    staged_plugins = os.path.join(staging_parent, os.path.basename(installed_plugins))
    required_bytes = install_entry_copy_size(bundled_plugins)
    with reservation_provider.reserve_disk_space(
        path=staging_parent,
        required_bytes=required_bytes,
        operation="application_updater.stage_configured_plugins",
        details={},
    ) as reservation:
        with claim_reserved_write(reservation, size_bytes=required_bytes):
            copy_install_entry(bundled_plugins, staging_parent)
            copied_path = os.path.join(staging_parent, os.path.basename(bundled_plugins))
            if copied_path != staged_plugins:
                os.rename(copied_path, staged_plugins)
    reconcile_staged_plugins(
        installed_plugins=installed_plugins,
        staged_plugins=staged_plugins,
        target_version=target_version,
        reservation_provider=reservation_provider,
    )
    require_disk_space_for_update(installed_plugins, install_entry_copy_size(staged_plugins), 0)
    return staged_plugins
