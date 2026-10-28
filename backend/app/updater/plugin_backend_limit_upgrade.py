"""SoAI - Transactional offline plugin backend limit refresh [backend/app/updater/plugin_backend_limit_upgrade.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import os
import stat
from collections.abc import Generator, Mapping
from contextlib import ExitStack, contextmanager
from typing import TYPE_CHECKING

from app.backup.backup_removal import sync_remove_tree_no_symlinks
from app.backup.restore_destinations import ensure_restore_destination_is_safe
from app.config.io import ConfigIO, ConfigIODependencies
from app.updater.plugin_backend_limit_upgrade_records import (
    DeclaredPluginBackendLimit,
    PluginBackendLimitRefreshResult,
    PreparedPluginBackendLimit,
)
from app.updater.software_update.plugin_reconciliation import reconcile_staged_plugins
from core.bootstrap.install_diagnostics import read_install_diagnostics_context
from core.bootstrap.install_payload_transaction import copy_install_entry
from core.bootstrap.install_target_windows import retain_windows_install_ancestors
from core.config.locks import ConfigLockTimeout, get_lock_path, get_plugin_config_mutation_lock_path
from core.config.value_validation import is_config_dict
from core.config.yaml_factory import build_roundtrip_yaml
from core.errors.exceptions import ConfigurationError, StateError, ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.locking import guarded_file_lock
from core.files.temp_files import create_secure_temp_directory
from core.filesystem.atomic_binary_writes import atomic_write_binary_content
from core.filesystem.atomic_write_primitives import fsync_directory
from core.filesystem.file_sync import fsync_install_entry
from core.filesystem.open_files import read_regular_file_snapshot_no_symlink
from core.filesystem.path_coercion import normalize_filesystem_path
from core.filesystem.windows_access_control import copy_windows_discretionary_acl
from core.hardware.reservation_claims import claim_reserved_write
from core.plugins.file_suffixes import PLUGIN_FILE_SUFFIX
from core.serialization.json import normalize_for_json
from core.types.json_value import require_json_dict
from plugins.manifest.ast_contracts import (
    eval_required_literal,
    extract_class_assignments,
    get_plugin_class_node,
)
from plugins.manifest.class_field_contract import PLUGIN_FIELD_DEFAULT_CONFIGURATION
from plugins.package_inspection import inspect_plugin_package_file

if TYPE_CHECKING:
    from core.hardware.protocols_storage import (
        DiskSpaceReservationLeaseProtocol,
        StorageManagerProtocol,
    )
    from core.logging.protocols import LoggerProtocol

__all__ = ("refresh_plugin_backend_limits",)

BACKEND_LIMIT_KEY = "MAX_SUPPORTED_BACKEND_VERSION"


def _inspect_declarations(directories: tuple[str, ...]) -> tuple[DeclaredPluginBackendLimit, ...]:
    declarations: list[DeclaredPluginBackendLimit] = []
    seen: set[tuple[int, int]] = set()
    for directory in directories:
        if not os.path.lexists(normalize_filesystem_path(directory)):
            continue
        ensure_restore_destination_is_safe(directory)
        if not os.path.isdir(normalize_filesystem_path(directory)):
            raise ValidationError("Plugin storage must be a directory.")
        directory_status = os.stat(normalize_filesystem_path(directory), follow_symlinks=False)
        directory_identity = (directory_status.st_dev, directory_status.st_ino)
        if directory_identity in seen:
            continue
        seen.add(directory_identity)
        for name in sorted(os.listdir(normalize_filesystem_path(directory))):
            if not name.endswith(PLUGIN_FILE_SUFFIX):
                continue
            path = os.path.join(directory, name)
            snapshot, identity = inspect_plugin_package_file(path)
            assignments = extract_class_assignments(
                get_plugin_class_node(snapshot.content.entrypoint.parsed_source)
            )
            if PLUGIN_FIELD_DEFAULT_CONFIGURATION not in assignments:
                continue
            defaults = eval_required_literal(assignments, PLUGIN_FIELD_DEFAULT_CONFIGURATION)
            if not isinstance(defaults, dict) or BACKEND_LIMIT_KEY not in defaults:
                continue
            defaults = require_json_dict(defaults, label="plugin defaults")
            limit = defaults[BACKEND_LIMIT_KEY]
            if not isinstance(limit, str):
                raise ValidationError(
                    "A plugin backend version limit must be a string.", details={"package": path}
                )
            declarations.append(DeclaredPluginBackendLimit(path, identity, snapshot, limit))
    return tuple(declarations)


def _prepare(
    declaration: DeclaredPluginBackendLimit, config_io: ConfigIO
) -> PreparedPluginBackendLimit | None:
    path = f"{declaration.package_path}.yaml"
    if not os.path.lexists(normalize_filesystem_path(path)):
        return None
    ensure_restore_destination_is_safe(path)
    original, identity = read_regular_file_snapshot_no_symlink(path)
    try:
        contents = original.decode("utf-8")
    except UnicodeDecodeError as exception:
        raise ConfigurationError(
            "Plugin configuration must be valid UTF-8.", details={"path": path}
        ) from exception
    mapping = config_io.parse_config_contents(
        contents, config_name=os.path.basename(declaration.package_path), config_path=path
    )
    if not is_config_dict(mapping):
        raise ConfigurationError("Plugin configuration contains unsupported values.")
    expected = require_json_dict(normalize_for_json(mapping), label="plugin configuration")
    if expected.get(BACKEND_LIMIT_KEY) == declaration.limit:
        return None
    expected[BACKEND_LIMIT_KEY] = declaration.limit
    mapping[BACKEND_LIMIT_KEY] = declaration.limit
    yaml_writer = build_roundtrip_yaml()
    yaml_writer.line_break = "\r\n" if "\r\n" in contents else "\n"
    stream = io.StringIO()
    yaml_writer.dump(mapping, stream)
    proposed = ("\ufeff" if contents.startswith("\ufeff") else "") + stream.getvalue()
    validated = config_io.parse_config_contents(
        proposed, config_name=os.path.basename(path), config_path=path
    )
    if normalize_for_json(validated) != expected:
        raise ConfigurationError("Plugin limit refresh would change other configuration values.")
    return PreparedPluginBackendLimit(
        path, original, identity, stat.S_IMODE(identity.mode), mapping, proposed
    )


def _revalidate(
    declarations: tuple[DeclaredPluginBackendLimit, ...],
    prepared: tuple[PreparedPluginBackendLimit, ...],
) -> None:
    for declaration in declarations:
        ensure_restore_destination_is_safe(declaration.package_path)
        snapshot, identity = inspect_plugin_package_file(declaration.package_path)
        if (
            not declaration.package_identity.matches_descriptor_snapshot(identity)
            or snapshot.content.archive_hash != declaration.snapshot.content.archive_hash
        ):
            raise StateError("Plugin package changed before configuration publication.")
    for entry in prepared:
        ensure_restore_destination_is_safe(entry.config_path)
        contents, identity = read_regular_file_snapshot_no_symlink(entry.config_path)
        if contents != entry.original or not entry.identity.matches_descriptor_snapshot(identity):
            raise StateError("Plugin configuration changed before publication.")


def _restore(
    attempted: list[PreparedPluginBackendLimit],
    originals: str,
    reservations: Mapping[str, DiskSpaceReservationLeaseProtocol],
) -> None:
    failures: dict[str, str] = {}
    for index, entry in reversed(tuple(enumerate(attempted))):
        try:
            current, identity = read_regular_file_snapshot_no_symlink(entry.config_path)
            if entry.matches_original(current, identity):
                continue
            if current not in (entry.original, entry.proposed.encode("utf-8")):
                raise StateError("Plugin configuration changed after publication.")
            with claim_reserved_write(
                reservations[entry.config_path], size_bytes=len(entry.original)
            ):
                atomic_write_binary_content(
                    entry.config_path,
                    entry.original,
                    file_mode=entry.permissions,
                    fsync_parent_directory=True,
                    preserve_windows_acl=True,
                )
                if os.name == "nt":
                    copy_windows_discretionary_acl(
                        os.path.join(originals, str(index), os.path.basename(entry.config_path)),
                        entry.config_path,
                    )
                fsync_install_entry(entry.config_path)
                fsync_directory(os.path.dirname(entry.config_path), strict=True)
                restored, identity = read_regular_file_snapshot_no_symlink(entry.config_path)
                if not entry.matches_original(restored, identity):
                    raise StateError("Plugin configuration restoration could not be verified.")
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            failures[entry.config_path] = str(exception)
    if failures:
        raise StateError(
            "Plugin configuration restoration failed; retained originals require repair.",
            details={"failed_paths": failures, "originals": originals},
        )


@contextmanager
def refresh_plugin_backend_limits(
    *,
    base_path: str,
    config_path: str,
    directories: tuple[str, ...],
    lock_directory: str,
    target_version: str,
    reservation_provider: StorageManagerProtocol,
    logger: LoggerProtocol,
    retained_packages: dict[str, str] | None = None,
) -> Generator[PluginBackendLimitRefreshResult]:
    with ExitStack() as locks:
        ordered_paths = sorted(set(directories), key=lambda path: (os.path.normcase(path), path))
        directories = tuple(ordered_paths)
        for directory in directories:
            retain_windows_install_ancestors(directory, locks)
            locks.enter_context(
                guarded_file_lock(
                    get_plugin_config_mutation_lock_path(directory, lock_directory=lock_directory),
                    timeout=30,
                    on_timeout=StateError(
                        "Plugin configuration mutation lock acquisition timed out."
                    ),
                )
            )
        if retained_packages is not None:
            for directory, original in retained_packages.items():
                reconcile_staged_plugins(
                    installed_plugins=original,
                    staged_plugins=directory,
                    target_version=target_version,
                    reservation_provider=reservation_provider,
                    preserve_configurations=False,
                )
        declarations = _inspect_declarations(directories)
        for path in sorted(
            {f"{declaration.package_path}.yaml" for declaration in declarations},
            key=lambda path: (os.path.normcase(path), path),
        ):
            locks.enter_context(
                guarded_file_lock(
                    get_lock_path(path, lock_directory=lock_directory),
                    timeout=5,
                    on_timeout=ConfigLockTimeout(
                        "Could not acquire plugin configuration lock.", config_path=path
                    ),
                )
            )
        config_io = ConfigIO(
            ConfigIODependencies(base_path, config_path, None, lock_directory, logger)
        )
        prepared = tuple(
            entry
            for declaration in declarations
            if (entry := _prepare(declaration, config_io)) is not None
        )
        if not prepared:
            yield PluginBackendLimitRefreshResult((), None)
            return
        diagnostics = read_install_diagnostics_context()
        originals = create_secure_temp_directory(
            prefix="soai-plugin-limits.",
            directory=diagnostics.directory if diagnostics is not None else None,
        )
        logger.info("Retaining plugin configuration originals at %s.", originals)
        attempted: list[PreparedPluginBackendLimit] = []
        with ExitStack() as reservations:
            original_bytes = sum(len(entry.original) for entry in prepared)
            original_reservation = reservations.enter_context(
                reservation_provider.reserve_disk_space(
                    path=originals,
                    required_bytes=original_bytes,
                    operation="plugin_backend_limit.originals",
                    details={},
                )
            )
            replacement_reservations = {
                entry.config_path: reservations.enter_context(
                    reservation_provider.reserve_disk_space(
                        path=entry.config_path,
                        required_bytes=len(entry.original) + len(entry.proposed.encode("utf-8")),
                        operation="plugin_backend_limit.replacement",
                        details={},
                    )
                )
                for entry in prepared
            }
            with claim_reserved_write(original_reservation, size_bytes=original_bytes):
                for index, entry in enumerate(prepared):
                    parent = os.path.join(originals, str(index))
                    copy_install_entry(entry.config_path, parent)
                    retained, identity = read_regular_file_snapshot_no_symlink(
                        os.path.join(parent, os.path.basename(entry.config_path))
                    )
                    if not entry.matches_original(retained, identity):
                        raise StateError("Retained configuration differs from its snapshot.")
                    fsync_install_entry(parent)
                fsync_directory(originals, strict=True)
            _revalidate(declarations, prepared)
            with ExitStack() as rollback:
                rollback.callback(_restore, attempted, originals, replacement_reservations)
                for entry in prepared:
                    _revalidate(declarations, (entry,))
                    with claim_reserved_write(
                        replacement_reservations[entry.config_path],
                        size_bytes=len(entry.proposed.encode("utf-8")),
                    ):
                        attempted.append(entry)
                        config_io.atomic_write_yaml_unlocked_sync(
                            config_path=entry.config_path,
                            config_mapping=entry.mapping,
                            backup_path=None,
                            encoding="utf-8",
                            serialized_contents=entry.proposed,
                        )
                        fsync_install_entry(entry.config_path)
                        fsync_directory(os.path.dirname(entry.config_path), strict=True)
                        published, _identity = read_regular_file_snapshot_no_symlink(
                            entry.config_path
                        )
                        if published != entry.proposed.encode("utf-8"):
                            raise StateError(
                                "Plugin backend limit publication could not be verified."
                            )
                yield PluginBackendLimitRefreshResult(
                    tuple(entry.config_path for entry in prepared), originals
                )
                rollback.pop_all()
        try:
            sync_remove_tree_no_symlinks(originals)
        except OSError as exception:
            logger.warning("Plugin originals cleanup failed: %s (%s)", originals, str(exception))
