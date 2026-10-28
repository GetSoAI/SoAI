"""SoAI - Protected native installation upgrade preparation [backend/app/updater/installation_upgrade_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from app.cli.offline_mode import resolve_config_path
from app.config.io import ConfigIO, ConfigIODependencies
from app.updater.plugin_backend_limit_upgrade_ownership import guard_plugin_upgrade_ownership
from app.updater.software_update.activation_state import (
    find_pending_update_activation,
    read_update_activation_identity,
    record_update_activation_identity,
)
from app.updater.software_update.install_transaction_persisted_state import (
    resolve_update_plugins_path,
    resolve_update_state_files,
)
from app.updater.software_update.install_transaction_preparation import prepare_update_rollback
from app.updater.software_update.install_transaction_recovery import (
    recover_unarmed_update_transaction,
)
from app.updater.software_update.install_transaction_state import (
    ROLLBACK_REQUIRED_MARKER,
    UpdateTransactionPaths,
    allocate_update_transaction,
    write_marker,
)
from app.updater.software_update.plugin_reconciliation import reconcile_staged_plugins
from app.updater.windows_installer_preparation import (
    retain_windows_recovery_runtime,
    verify_windows_installer_original_backup,
)
from core.bootstrap.disk_reservation_provider import create_bootstrap_disk_reservation_provider
from core.bootstrap.install_locks import inherited_install_lock_is_valid
from core.bootstrap.install_payload import managed_root_entries
from core.bootstrap.install_payload_transaction import copy_install_entry, install_entry_copy_size
from core.bootstrap.venv_paths import get_venv_path
from core.config.runtime_config import Config
from core.config.value_validation import is_config_dict
from core.errors.exceptions import StateError
from core.filesystem.file_sync import fsync_install_entry
from core.filesystem.open_files import read_regular_file_no_symlink
from core.logging.protocols import LoggerProtocol
from core.meta.paths import join_data_abs
from core.tasks.software_update_result import (
    create_software_update_task_id,
)

__all__ = ("prepare_owned_installation_upgrade",)


def prepare_owned_installation_upgrade(
    *,
    base_path: str,
    source: str,
    staged: str,
    edition: str,
    original_root: str,
    retained_installation_root: str | None,
    native_backup_root: str | None,
    allocated: list[UpdateTransactionPaths],
    logger: LoggerProtocol,
) -> None:
    with guard_plugin_upgrade_ownership(base_path, edition=edition, logger=logger):
        provider = create_bootstrap_disk_reservation_provider(base_path)
        target_version = (
            read_regular_file_no_symlink(os.path.join(source, "VERSION"), max_bytes=128)
            .decode("utf-8")
            .strip()
        )
        prepared = find_pending_update_activation(base_path, include_preparation=True)
        if prepared is not None and not os.path.isfile(
            os.path.join(prepared.paths.transaction_path, ROLLBACK_REQUIRED_MARKER)
        ):
            recover_unarmed_update_transaction(
                prepared.paths,
                logger,
                cause=StateError("Installer preparation was interrupted."),
                retained_installation_root=retained_installation_root,
                installation_lock_held=True,
            )
            prepared = None
        if prepared is None:
            config_path = resolve_config_path(base_path)
            config_source = (
                config_path
                if os.path.lexists(config_path)
                else join_data_abs(source, "config", "config.default.yaml")
            )
            io_owner = ConfigIO(
                ConfigIODependencies(
                    base_path=base_path,
                    core_config_path=config_path,
                    plugins_path=None,
                    lock_directory=None,
                    logger=logger,
                )
            )
            payload = io_owner.parse_config_contents(
                read_regular_file_no_symlink(config_source).decode("utf-8"),
                config_name="config",
                config_path=config_source,
            )
            if not is_config_dict(payload):
                raise StateError("Installer configuration contains unsupported values.")
            config = Config(payload, main_app_base_dir=base_path)
            plugins = resolve_update_plugins_path(config)
            paths = allocate_update_transaction(
                base_path,
                installation_lock_held=True,
                inherited_install_lock_validator=inherited_install_lock_is_valid,
            )
            allocated.append(paths)
            record_update_activation_identity(
                paths,
                task_id=create_software_update_task_id(),
                edition=edition,
                from_version=read_regular_file_no_symlink(
                    os.path.join(original_root, "VERSION"), max_bytes=128
                )
                .decode("utf-8")
                .strip(),
                to_version=target_version,
                config_path=config_path,
            )
            data = join_data_abs(paths.staged_new_path)
            required_bytes = sum(
                install_entry_copy_size(join_data_abs(source, entry))
                for entry in ("vendor", "config")
            )
            with provider.reserve_disk_space(
                path=paths.staged_new_path,
                required_bytes=required_bytes,
                operation="installer.upgrade_staging",
            ) as reservation:
                with reservation.claim_write_bytes(required_bytes) as claim:
                    copy_install_entry(join_data_abs(source, "vendor"), data)
                    os.makedirs(os.path.join(data, "config"), mode=0o700)
                    copy_install_entry(
                        join_data_abs(source, "config", "config.default.yaml"),
                        os.path.join(data, "config"),
                    )
                    fsync_install_entry(data)
                    claim.commit()
            roots = tuple(
                entry
                for entry in managed_root_entries(edition)
                if os.path.lexists(os.path.join(staged, entry))
                or os.path.lexists(os.path.join(original_root, entry))
            )
            directories: tuple[str, ...] = (get_venv_path(base_path),)
            if os.path.normcase(plugins) != os.path.normcase(os.path.join(base_path, "plugins")):
                directories += (plugins,)
            prepare_update_rollback(
                paths,
                identity=read_update_activation_identity(paths),
                state_files=resolve_update_state_files(config, config_path),
                state_directories=directories,
                additional_roots=roots,
                retained_installation_root=retained_installation_root,
            )
            if os.name == "nt":
                retain_windows_recovery_runtime(paths, provider)
            if native_backup_root is not None:
                verify_windows_installer_original_backup(paths, native_backup_root)
            write_marker(paths.transaction_path, ROLLBACK_REQUIRED_MARKER)
        else:
            if prepared.edition != edition or prepared.to_version != target_version:
                raise StateError("Installer upgrade conflicts with the protected update identity.")
        reconcile_staged_plugins(
            installed_plugins=os.path.join(original_root, "plugins"),
            staged_plugins=os.path.join(staged, "plugins"),
            target_version=target_version,
            reservation_provider=provider,
            preserve_configurations=os.path.normcase(staged) != os.path.normcase(base_path),
        )
