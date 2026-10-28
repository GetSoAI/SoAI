"""SoAI - Installer plugin selection and protected upgrade lifecycle [backend/app/updater/installation_plugin_upgrade.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import argparse
import os

from app.backup.restore_destinations import ensure_restore_destination_is_safe
from app.updater.installation_upgrade_preparation import prepare_owned_installation_upgrade
from app.updater.plugin_backend_limit_upgrade_ownership import guard_plugin_upgrade_ownership
from app.updater.software_update.activation_state import (
    find_pending_update_activation,
    prepare_update_activation,
    require_armed_update_transaction,
)
from app.updater.software_update.install_transaction import TRANSACTION_COMMIT_EXCEPTIONS
from app.updater.software_update.install_transaction_inventory import (
    require_retained_installation_root,
)
from app.updater.software_update.install_transaction_recovery import (
    UpdateRepairRequiredError,
    recover_unarmed_update_transaction,
    restore_transaction,
)
from app.updater.software_update.install_transaction_state import (
    NEW_COMPLETE_MARKER,
    ROLLBACK_REQUIRED_MARKER,
    AppliedUpdateTransaction,
    UpdateTransactionPaths,
    build_rollback_top_level_ignore_patterns,
    write_marker,
)
from app.updater.software_update.update_lock import resolve_software_update_lock_dir
from core.bootstrap.filename_normalization import (
    normalize_installed_filenames,
    normalized_filenames_are_usable,
    validate_filename_destinations,
)
from core.bootstrap.install_payload import INSTALL_MANIFEST_FILENAME
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.logging.trace import get_logger
from core.tasks.software_update_result import (
    write_software_update_result,
)

__all__ = ("prepare_installation_plugin_upgrade", "finish_installation_plugin_upgrade")

LOGGER_NAME = "SoAI.app.updater.installation_plugin_upgrade"
OPERATION_FRESH_INSTALLATION_CLEANUP = "installation_upgrade.fresh_filename_cleanup"


def prepare_installation_plugin_upgrade(
    *,
    base_path: str,
    source: str,
    staged: str,
    edition: str,
    retained_installation_root: str | None = None,
    native_backup_root: str | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if native_backup_root is not None and retained_installation_root is not None:
        raise StateError(
            "Live-source preparation and retained-source recovery are separate operations."
        )
    original_root = retained_installation_root or base_path
    validate_filename_destinations(staged, base_path, previous_root=original_root)
    for directory in (base_path, source, staged, original_root):
        ensure_restore_destination_is_safe(directory)
        if not os.path.isdir(directory):
            raise StateError("Installer upgrade paths must be regular directories.")
    if retained_installation_root is not None:
        require_retained_installation_root(base_path, original_root, edition=edition)
    if not any(
        os.path.isfile(os.path.join(original_root, *components))
        for components in (("backend", "main.py"), (INSTALL_MANIFEST_FILENAME,))
    ):
        return
    allocated: list[UpdateTransactionPaths] = []
    try:
        prepare_owned_installation_upgrade(
            base_path=base_path,
            source=source,
            staged=staged,
            edition=edition,
            original_root=original_root,
            retained_installation_root=retained_installation_root,
            native_backup_root=native_backup_root,
            allocated=allocated,
            logger=logger,
        )
    except UpdateRepairRequiredError:
        raise
    except TRANSACTION_COMMIT_EXCEPTIONS as exception:
        if allocated:
            recover_unarmed_update_transaction(
                allocated[0],
                logger,
                cause=exception,
                retained_installation_root=retained_installation_root,
            )
        raise


def finish_installation_plugin_upgrade(
    base_path: str,
    *,
    edition: str,
    success: bool,
    retained_installation_root: str | None = None,
    cleanup_after_recovery: bool = True,
) -> None:
    logger = get_logger(LOGGER_NAME)
    with guard_plugin_upgrade_ownership(base_path, edition=edition, logger=logger):
        if os.path.lexists(resolve_software_update_lock_dir(base_path)):
            return
        pending = find_pending_update_activation(base_path, include_preparation=True)
        if pending is None:
            if success:
                try:
                    normalize_installed_filenames(base_path)
                except OSError as exception:
                    if not normalized_filenames_are_usable(base_path):
                        raise
                    log_exception(
                        logger,
                        exception,
                        message="Installation is usable; filename cleanup remains pending for the next startup.",
                        operation=OPERATION_FRESH_INSTALLATION_CLEANUP,
                        level="warning",
                    )
            return
        if pending.edition != edition:
            raise StateError("Installer completion edition conflicts with its protected state.")
        if success:
            require_armed_update_transaction(pending.paths)
            write_marker(pending.paths.transaction_path, NEW_COMPLETE_MARKER)
            prepare_update_activation(
                AppliedUpdateTransaction(base_path, pending.paths.transaction_path)
            )
            write_software_update_result(
                base_path,
                task_id=pending.task_id,
                from_version=pending.from_version,
                to_version=pending.to_version,
                status="installing",
                message=f"Updating to v{pending.to_version}",
            )
        elif not os.path.isfile(
            os.path.join(pending.paths.transaction_path, ROLLBACK_REQUIRED_MARKER)
        ):
            recover_unarmed_update_transaction(
                pending.paths,
                logger,
                cause=StateError("Installer preparation did not complete."),
                retained_installation_root=retained_installation_root,
                cleanup_after_recovery=cleanup_after_recovery,
                installation_lock_held=True,
            )
        elif not restore_transaction(
            paths=pending.paths,
            top_level_ignore_patterns=build_rollback_top_level_ignore_patterns(
                pending.paths.transaction_path
            ),
            logger=logger,
            cleanup_after_recovery=os.name != "nt",
        ):
            raise StateError(
                "Installer state restoration failed; retained originals require repair."
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("prepare", "finish", "abort"))
    parser.add_argument("--base-path", required=True)
    parser.add_argument("--edition", required=True)
    parser.add_argument("--source")
    parser.add_argument("--staged")
    parser.add_argument("--retained-installation-root")
    arguments = parser.parse_args()
    if arguments.operation == "prepare":
        if not arguments.source or not arguments.staged:
            parser.error("prepare requires --source and --staged")
        prepare_installation_plugin_upgrade(
            base_path=os.path.abspath(arguments.base_path),
            source=os.path.abspath(arguments.source),
            staged=os.path.abspath(arguments.staged),
            edition=arguments.edition,
            retained_installation_root=arguments.retained_installation_root,
        )
    else:
        finish_installation_plugin_upgrade(
            os.path.abspath(arguments.base_path),
            edition=arguments.edition,
            success=arguments.operation == "finish",
            retained_installation_root=arguments.retained_installation_root,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
