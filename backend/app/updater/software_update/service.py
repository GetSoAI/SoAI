"""SoAI - Software update check and install service [backend/app/updater/software_update/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.updater.dependencies import SoftwareUpdateServiceDependencies
from app.updater.software_update.check_logging import log_software_update_check_result
from app.updater.software_update.install_flow import run_software_update_install_flow
from app.updater.software_update.install_transaction_recovery import (
    recover_interrupted_update_transactions,
)
from app.updater.software_update.status_query import (
    get_software_update_status_for_dependencies,
)
from app.updater.software_update.target_validation import validate_update_target
from app.updater.software_update.update_lock import guarded_software_update_lock
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError, ValidationError

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("SoftwareUpdateService",)

OPERATION_APPLICATION_UPDATER_RUN_SOFTWARE_UPDATE_LOCK = (
    "application_updater.run_software_update.lock"
)


class SoftwareUpdateService:
    def __init__(self, deps: SoftwareUpdateServiceDependencies) -> None:
        self._deps = deps

    def get_software_update_status(self) -> tuple[JSONDict, JSONDict] | None:
        return get_software_update_status_for_dependencies(self._deps)

    def run_software_update_check(self) -> int:
        deps = self._deps
        deps.logger.info("%s\nChecking for SoAI Software Updates\n%s", "=" * 60, "=" * 60)
        if not deps.local_version:
            return 1
        update_info = self.get_software_update_status()
        if not update_info:
            return 1
        update_status, latest_release = update_info
        log_software_update_check_result(
            logger=deps.logger,
            local_version=deps.local_version,
            update_status=update_status,
            latest_release=latest_release,
        )
        return 0

    def run_software_update(self) -> int:
        deps = self._deps
        deps.logger.info(
            "%s\nSoAI Software Updater Started\nPlatform: %s\nBase Path: %s\n%s",
            "=" * 60,
            deps.platform_name,
            deps.base_path,
            "=" * 60,
        )
        try:
            with guarded_software_update_lock(
                base_path=deps.base_path,
                platform_name=deps.platform_name,
                logger=deps.logger,
            ):
                if not recover_interrupted_update_transactions(deps.base_path, deps.logger):
                    deps.logger.error("Update aborted: interrupted update recovery failed.")
                    return 1
                if not validate_update_target(
                    deps.logger,
                    config_path=deps.config_path,
                    main_py_path=deps.main_py_path,
                ):
                    return 1
                return run_software_update_install_flow(deps)
        except OSError as exception:
            log_exception(
                deps.logger,
                exception,
                message="Software update lock operation failed.",
                operation=OPERATION_APPLICATION_UPDATER_RUN_SOFTWARE_UPDATE_LOCK,
            )
            return 1
        except StateError as exception:
            log_handled_exception(
                deps.logger,
                exception,
                message="Software update state validation failed.",
                operation=OPERATION_APPLICATION_UPDATER_RUN_SOFTWARE_UPDATE_LOCK,
                level="error",
            )
            return 1
        except ValidationError as exception:
            log_handled_exception(
                deps.logger,
                exception,
                message="Software update validation failed.",
                operation=OPERATION_APPLICATION_UPDATER_RUN_SOFTWARE_UPDATE_LOCK,
                level="error",
            )
            return 1
