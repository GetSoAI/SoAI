"""SoAI - Locked software update install flow [backend/app/updater/software_update/install_flow.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.updater.dependencies import SoftwareUpdateServiceDependencies
from app.updater.release_bundle import prepare_release_bundle
from app.updater.release_manifest_types import ReleaseInstaller
from app.updater.service_config_loading import require_unchanged_update_configuration
from app.updater.soai_process import start_soai, stop_running_instance
from app.updater.software_install import perform_update
from app.updater.software_update.activation_supervision import supervise_update_activation
from app.updater.software_update.handoff import announce_prepared_updater, clear_updater_handoff
from app.updater.software_update.install_transaction_recovery import (
    recover_interrupted_update_transactions,
)
from app.updater.software_update.status_query import (
    get_software_update_status_for_dependencies,
)
from app.updater.software_update_task_logging import log_software_update_task_for_dependencies
from app.updater.windows_installer_update import perform_windows_installer_update
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.tasks.software_update_result import (
    create_software_update_task_id,
    write_software_update_result,
)
from core.timing.constants import RESPONSIVE_TIMEOUT_SEC
from core.timing.sleep import sleep_seconds
from core.validation.boolean_coercion import coerce_bool_with_default
from database.migrations.runtime import validate_database_path_for_upgrade

__all__ = ("run_software_update_install_flow",)

OPERATION = "application_updater.run_software_update"
OPERATION_RESULT = "application_updater.run_software_update.persist_result"


def _record_update_result(
    deps: SoftwareUpdateServiceDependencies,
    *,
    task_id: str,
    from_version: str,
    to_version: str,
    status: str,
    message: str,
) -> bool:
    try:
        write_software_update_result(
            deps.base_path,
            task_id=task_id,
            from_version=from_version,
            to_version=to_version,
            status=status,
            message=message,
        )
        return True
    except OSError as exception:
        log_exception(
            deps.logger,
            exception,
            message="Software update result could not be persisted.",
            operation=OPERATION_RESULT,
            level="error",
        )
        return False


def _restart_after_failed_update(
    deps: SoftwareUpdateServiceDependencies,
    *,
    should_restart: bool,
) -> None:
    if should_restart and (not deps.args.no_restart):
        if not recover_interrupted_update_transactions(deps.base_path, deps.logger):
            deps.logger.error(
                "SoAI was not restarted because update recovery still requires repair."
            )
            return
        deps.logger.info("Restarting SoAI (previous version)...")
        sleep_seconds(RESPONSIVE_TIMEOUT_SEC)
        start_soai(
            logger=deps.logger,
            platform_name=deps.platform_name,
            base_path=deps.base_path,
            main_py_path=deps.main_py_path,
            config_path=deps.config_path,
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
            config_path=deps.config_path,
        )


def run_software_update_install_flow(deps: SoftwareUpdateServiceDependencies) -> int:
    platform_id = deps.platform_id
    should_restart = deps.args.wait_for_pid is not None and deps.args.task_id is None
    if platform_id is None:
        deps.logger.error("Automatic software updates do not support this platform.")
        _restart_after_failed_update(deps, should_restart=should_restart)
        return 1
    task_id = deps.args.task_id or create_software_update_task_id()
    update_success = False
    installer_handoff_started = False
    result_record_started = False
    latest_version = deps.local_version or "unknown"
    cancelled = False

    def quiesce_installation() -> bool:
        nonlocal should_restart, cancelled
        require_unchanged_update_configuration(
            config_path=deps.config_path,
            base_path=deps.base_path,
            prepared_config=deps.config,
            module_dependencies=deps.module_dependencies,
        )
        if deps.args.task_id is not None:
            announce_prepared_updater(
                base_path=deps.base_path, task_id=task_id, edition=deps.updater.edition
            )
        stop_result = stop_running_instance(deps, task_id=task_id, latest_version=latest_version)
        should_restart = stop_result.should_restart
        cancelled = stop_result.cancelled
        if stop_result.can_continue:
            require_unchanged_update_configuration(
                config_path=deps.config_path,
                base_path=deps.base_path,
                prepared_config=deps.config,
                module_dependencies=deps.module_dependencies,
            )
        return stop_result.can_continue

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
                if deps.args.task_id is not None:
                    _record_update_result(
                        deps,
                        task_id=task_id,
                        from_version=deps.local_version,
                        to_version=latest_version,
                        status="cancelled",
                        message="The installation is already up-to-date.",
                    )
                    return 0
                _restart_after_successful_update(deps, should_restart=should_restart)
                return 0
            release_bundle = prepare_release_bundle(
                release_info=latest_release,
                version=latest_version,
                platform_id=platform_id,
                timeout=deps.timeout,
                updater=deps.updater,
            )
            validate_database_path_for_upgrade(deps.config.get_str("DATA.DATABASE.PATHS.SYSTEM_DB"))
            result_record_started = _record_update_result(
                deps,
                task_id=task_id,
                from_version=deps.local_version or "0.0.0",
                to_version=latest_version,
                status="installing",
                message=f"Updating to v{latest_version}",
            )
            if not result_record_started:
                update_result = False
            elif isinstance(release_bundle.artifact_record, ReleaseInstaller):
                update_result = perform_windows_installer_update(
                    logger=deps.logger,
                    base_path=deps.base_path,
                    temp_path=deps.temp_path,
                    config=deps.config,
                    config_path=deps.config_path,
                    download_timeout=deps.download_timeout,
                    release_bundle=release_bundle,
                    reservation_provider=deps.storage_manager,
                    restart_after_update=lambda: should_restart and not deps.args.no_restart,
                    before_handoff=quiesce_installation,
                    task_id=task_id,
                    from_version=deps.local_version or "0.0.0",
                )
                installer_handoff_started = update_result is True
            else:
                update_result = perform_update(
                    logger=deps.logger,
                    base_path=deps.base_path,
                    temp_path=deps.temp_path,
                    platform_id=platform_id,
                    config=deps.config,
                    config_path=deps.config_path,
                    before_commit=quiesce_installation,
                    task_id=task_id,
                    from_version=deps.local_version or "0.0.0",
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
    finally:
        if deps.args.task_id is not None:
            clear_updater_handoff(deps.base_path, task_id)
    if cancelled:
        _record_update_result(
            deps,
            task_id=task_id,
            from_version=deps.local_version or "0.0.0",
            to_version=latest_version,
            status="cancelled",
            message="Software update cancelled before installation.",
        )
        return 0
    if not update_success:
        if result_record_started:
            _record_update_result(
                deps,
                task_id=task_id,
                from_version=deps.local_version or "0.0.0",
                to_version=latest_version,
                status="failed",
                message="Software update did not succeed.",
            )
        log_software_update_task_for_dependencies(
            deps,
            task_id=task_id,
            to_version=latest_version,
            status="failed",
            message="Update did not succeed.",
        )
        _restart_after_failed_update(deps, should_restart=should_restart)
        return 1
    if installer_handoff_started:
        return 0
    deps.logger.info("Update installed; completion awaits verified application activation.")
    if should_restart and not deps.args.no_restart:
        if not supervise_update_activation(deps):
            _restart_after_failed_update(deps, should_restart=True)
            return 1
    return 0
