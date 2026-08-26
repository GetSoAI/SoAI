"""SoAI - Locked software update install flow [backend/app/updater/software_update/install_flow.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from app.updater.dependencies import SoftwareUpdateServiceDependencies
from app.updater.release_bundle import prepare_release_bundle
from app.updater.soai_instance import (
    resolve_running_soai_pid,
    wait_for_instance_lock_release,
)
from app.updater.soai_process import start_soai, stop_soai, wait_for_pid_exit
from app.updater.software_install import perform_update
from app.updater.software_update.status_query import (
    get_software_update_status_for_dependencies,
)
from app.updater.software_update_task_logging import log_software_update_task
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.timing.constants import RESPONSIVE_TIMEOUT_SEC
from core.timing.sleep import sleep_seconds
from core.validation.boolean_coercion import coerce_bool_with_default

__all__ = ("run_software_update_install_flow",)

OPERATION = "application_updater.run_software_update"


@dataclass(frozen=True, slots=True)
class InstanceStopResult:
    can_continue: bool
    should_restart: bool
    cancelled: bool = False


def _stop_running_instance(
    deps: SoftwareUpdateServiceDependencies,
    *,
    latest_version: str,
) -> InstanceStopResult:
    should_restart = True
    if deps.args.wait_for_pid is not None:
        stopped = wait_for_pid_exit(
            logger=deps.logger,
            platform_name=deps.platform_name,
            pid=deps.args.wait_for_pid,
        )
        return InstanceStopResult(can_continue=stopped, should_restart=should_restart)
    is_running, running_pid = resolve_running_soai_pid(
        logger=deps.logger,
        base_path=deps.base_path,
        temp_path=deps.temp_path,
        platform_name=deps.platform_name,
        expected_edition=deps.updater.edition,
    )
    if not is_running:
        return InstanceStopResult(can_continue=True, should_restart=False)
    if running_pid is None:
        deps.logger.error(
            "SoAI appears to be running (instance lock is held), but updater could not determine its PID. Please stop SoAI manually and run updater again.",
        )
        return InstanceStopResult(can_continue=False, should_restart=should_restart)
    deps.logger.info("SoAI is running with PID: %s", running_pid)
    log_software_update_task(
        logger=deps.logger,
        api_client=deps.api_client,
        api_timeout=deps.api_timeout,
        from_version=deps.local_version or "unknown",
        to_version=latest_version,
        status="started",
        message=f"Updating from v{deps.local_version} to v{latest_version}",
    )
    if (not deps.args.silent) and input(
        "SoAI must be stopped to continue. Stop it now? (y/n): ",
    ).lower().strip() != "y":
        deps.logger.info("Update cancelled by user.")
        return InstanceStopResult(
            can_continue=False,
            should_restart=should_restart,
            cancelled=True,
        )
    if not stop_soai(
        logger=deps.logger,
        platform_name=deps.platform_name,
        soai_pid=running_pid,
    ):
        deps.logger.warning(
            "Failed to stop SoAI. Please stop it manually and run the updater again.",
        )
        return InstanceStopResult(can_continue=False, should_restart=should_restart)
    if not wait_for_instance_lock_release(
        logger=deps.logger,
        base_path=deps.base_path,
        timeout_sec=30.0,
    ):
        deps.logger.warning(
            "SoAI instance lock did not release after shutdown. Aborting update for safety.",
        )
        return InstanceStopResult(can_continue=False, should_restart=should_restart)
    return InstanceStopResult(can_continue=True, should_restart=should_restart)


def _restart_after_failed_update(
    deps: SoftwareUpdateServiceDependencies,
    *,
    should_restart: bool,
) -> None:
    if should_restart and (not deps.args.no_restart):
        deps.logger.info("Restarting SoAI (previous version)...")
        sleep_seconds(RESPONSIVE_TIMEOUT_SEC)
        start_soai(
            logger=deps.logger,
            platform_name=deps.platform_name,
            base_path=deps.base_path,
            main_py_path=deps.main_py_path,
        )


def _restart_after_successful_update(
    deps: SoftwareUpdateServiceDependencies,
    *,
    should_restart: bool,
) -> None:
    if should_restart and (not deps.args.no_restart):
        deps.logger.info("Restarting SoAI...")
        sleep_seconds(RESPONSIVE_TIMEOUT_SEC)
        start_soai(
            logger=deps.logger,
            platform_name=deps.platform_name,
            base_path=deps.base_path,
            main_py_path=deps.main_py_path,
        )


def run_software_update_install_flow(deps: SoftwareUpdateServiceDependencies) -> int:
    platform_id = deps.platform_id
    should_restart = deps.args.wait_for_pid is not None
    if platform_id is None:
        deps.logger.error("Automatic software updates do not support this platform.")
        _restart_after_failed_update(deps, should_restart=should_restart)
        return 1
    update_success = False
    latest_version = deps.local_version or "unknown"
    try:
        deps.logger.info("Fetching latest release information from GitHub...")
        update_info = get_software_update_status_for_dependencies(deps)
        if update_info:
            update_status, latest_release = update_info
            latest_version_value = update_status.get("latest_version")
            if isinstance(latest_version_value, str):
                latest_version = latest_version_value
            deps.logger.info("Latest version available on GitHub: v%s", latest_version)
            update_available = coerce_bool_with_default(
                update_status.get("update_available"),
                default=False,
                strict=False,
            )
            if deps.local_version and (not update_available):
                deps.logger.info("Your SoAI installation is already up-to-date.")
                _restart_after_successful_update(deps, should_restart=should_restart)
                return 0
            release_bundle = prepare_release_bundle(
                release_info=latest_release,
                version=latest_version,
                platform_id=platform_id,
                timeout=deps.timeout,
                updater=deps.updater,
            )
            stop_result = _stop_running_instance(deps, latest_version=latest_version)
            should_restart = stop_result.should_restart
            if not stop_result.can_continue:
                if stop_result.cancelled:
                    return 0
            else:
                update_result = perform_update(
                    logger=deps.logger,
                    base_path=deps.base_path,
                    temp_path=deps.temp_path,
                    platform_id=platform_id,
                    config=deps.config,
                    download_timeout=deps.download_timeout,
                    release_bundle=release_bundle,
                    reservation_provider=deps.storage_manager,
                )
                update_success = update_result is True
    except (StateError, ValidationError) as exception:
        log_handled_exception(
            deps.logger,
            exception,
            message="Software update validation failed.",
            operation=OPERATION,
            level="error",
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            deps.logger,
            exception,
            message="Software update failed",
            operation=OPERATION,
        )
    if not update_success:
        log_software_update_task(
            logger=deps.logger,
            api_client=deps.api_client,
            api_timeout=deps.api_timeout,
            from_version=deps.local_version or "unknown",
            to_version=latest_version,
            status="failed",
            message="Update did not succeed.",
        )
        _restart_after_failed_update(deps, should_restart=should_restart)
        return 1
    log_software_update_task(
        logger=deps.logger,
        api_client=deps.api_client,
        api_timeout=deps.api_timeout,
        from_version=deps.local_version or "unknown",
        to_version=latest_version,
        status="completed",
        message=f"Updated to v{latest_version}",
    )
    _restart_after_successful_update(deps, should_restart=should_restart)
    return 0
