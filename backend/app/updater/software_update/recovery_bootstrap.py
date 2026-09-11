"""SoAI - Verified runtime package selection for interrupted-update recovery [backend/app/updater/software_update/recovery_bootstrap.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys

from app.installation_transaction_admission import (
    TRANSACTION_PREFIX,
)
from app.updater.software_update.install_transaction_inventory import require_rollback_inventory
from app.updater.software_update.install_transaction_state import (
    OLD_COMPLETE_MARKER,
    ROLLBACK_COMPLETE_MARKER,
    ROLLBACK_REQUIRED_MARKER,
    SUCCESS_COMPLETE_MARKER,
    marker_path,
    paths_from_transaction_directory,
    validate_transaction_markers,
)
from core.bootstrap.venv_paths import get_venv_path, get_venv_site_package_paths
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SecurityError, StateError, ValidationError
from core.files.path_policy import safe_join_relative_under_base
from core.logging.trace import get_logger
from core.system.process_replacement import replace_current_process

__all__ = ("launch_update_recovery", "resolve_update_recovery_package_paths")

LOGGER_NAME = "SoAI.app.updater.recovery_bootstrap"
OPERATION_RECOVERY_BOOTSTRAP = "application_updater.recovery_bootstrap"


def resolve_update_recovery_package_paths(base_path: str) -> tuple[str, ...]:
    runtime_path = get_venv_path(base_path)
    retained_runtime: str | None = None
    for name in os.listdir(base_path):
        if not name.startswith(TRANSACTION_PREFIX):
            continue
        transaction_path = os.path.join(base_path, name)
        if os.path.islink(transaction_path) or not os.path.isdir(transaction_path):
            raise StateError("Update recovery storage is invalid; preserve it for repair.")
        validate_transaction_markers(transaction_path)
        if any(
            os.path.exists(marker_path(transaction_path, marker))
            for marker in (
                SUCCESS_COMPLETE_MARKER,
                ROLLBACK_COMPLETE_MARKER,
            )
        ):
            continue
        if not all(
            os.path.exists(marker_path(transaction_path, marker))
            for marker in (
                OLD_COMPLETE_MARKER,
                ROLLBACK_REQUIRED_MARKER,
            )
        ):
            continue
        paths = paths_from_transaction_directory(base_path, transaction_path)
        inventory = require_rollback_inventory(paths, old_complete=True)
        if inventory is None or inventory.runtime_directory is None:
            continue
        if os.path.normcase(inventory.runtime_directory) != os.path.normcase(runtime_path):
            raise StateError(
                "Restore the prior configured managed-runtime path before recovering this update."
            )
        if retained_runtime is not None:
            raise StateError(
                "Multiple retained runtimes require repair; recovery selection is ambiguous."
            )
        for slot, destination in inventory.persisted_state.destinations.items():
            if destination == inventory.runtime_directory:
                retained_runtime = safe_join_relative_under_base(
                    base_path=paths.rollback_old_path,
                    relative_path=slot,
                    description="Retained update runtime",
                    error_cls=StateError,
                )
                break
    selected_runtime = retained_runtime or runtime_path
    package_paths = get_venv_site_package_paths(selected_runtime)
    for package_path in package_paths:
        safe_join_relative_under_base(
            base_path=selected_runtime,
            relative_path=os.path.relpath(package_path, selected_runtime),
            description="Update recovery runtime packages",
            error_cls=StateError,
        )
        if not os.path.isdir(package_path):
            raise StateError(
                "Required recovery runtime packages are unavailable; preserve the update for repair."
            )
    return package_paths


def launch_update_recovery(base_path: str) -> int:
    base_path = os.path.abspath(base_path)
    package_paths = resolve_update_recovery_package_paths(base_path)
    recovery_backend = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    os.environ["PYTHONPATH"] = os.pathsep.join((recovery_backend, *package_paths))
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    if os.name == "nt":
        return replace_current_process(
            [
                sys.executable,
                "-P",
                "-S",
                "-c",
                """import sys
from app.updater.software_update.install_transaction_recovery import recover_interrupted_update_transactions
from core.logging.trace import get_logger
recovered = recover_interrupted_update_transactions(
    sys.argv[1], get_logger('SoAI.app.updater.recovery_bootstrap'),
    allow_pending_activation=True, cleanup_after_recovery=False,
)
raise SystemExit(0 if recovered else 1)
""",
                base_path,
            ]
        )
    return replace_current_process(
        [
            sys.executable,
            "-P",
            "-S",
            "-m",
            "app.updater.software_update.install_transaction_recovery",
            base_path,
        ]
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: update recovery bootstrap INSTALL_ROOT")
    try:
        raise SystemExit(launch_update_recovery(sys.argv[1]))
    except (OSError, SecurityError, StateError, ValidationError) as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Update recovery could not load verified runtime packages; preserve evidence for repair.",
            operation=OPERATION_RECOVERY_BOOTSTRAP,
        )
        raise SystemExit(1) from exception
