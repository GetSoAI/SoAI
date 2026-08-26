"""SoAI - Full application runtime CLI entrypoint [backend/app/cli/runtime_entrypoint.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import sys

from app.cli.application import run_application
from app.cli.dependencies import ApplicationDependencies
from app.cli.instance_lock.service import setup_pid_file_and_lock
from app.cli.offline_mode import OfflineModeResolver, resolve_config_path
from app.cli.process_control import finalize_and_force_exit
from app.cli.startup_flags import (
    apply_environment_flags,
    build_argument_parser,
    handle_information_cli_request,
    normalize_cli_args,
    resolve_startup_action,
)
from app.core_edition import build_core_edition_composition
from app.edition_composition import EditionComposition
from core.bootstrap.background_runtime_lock import (
    release_launcher_runtime_lock_if_owned,
)
from core.bootstrap.runtime_record_path import resolve_temp_directory_bootstrap
from core.bootstrap.stage0_environment import is_running_in_soai_venv
from core.bootstrap.venv_paths import get_venv_path
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.logging.bootstrap import setup_bootstrap_logger
from core.meta.paths import get_repo_root
from core.meta.version import __version__
from core.platform.os import is_windows
from core.prompts.system_prompts import load_system_prompts_catalog
from core.runtime.event_loop_runner import run_coroutine_in_new_event_loop
from core.runtime.windows_event_loop_policy import configure_windows_event_loop_policy
from core.system.privileges import is_admin
from core.system.resource_limits import configure_resource_limits
from core.validation.runtime import ensure_minimum_python_version

__all__ = ("runtime_entrypoint",)

OPERATION = "main.runtime_entrypoint"


def _prepare_runtime_arguments(arguments: list[str] | None) -> list[str]:
    program_name = sys.argv[0]
    provided_args = list(sys.argv[1:] if arguments is None else arguments)
    normalized_args = normalize_cli_args(provided_args)
    sys.argv = [program_name] + normalized_args
    return normalized_args


def _validate_start_action(normalized_args: list[str], lifecycle_logger: logging.Logger) -> bool:
    parser = build_argument_parser()
    parsed_args = parser.parse_args(normalized_args)
    action = resolve_startup_action(parsed_args)
    apply_environment_flags(parsed_args)
    if action == "start":
        return True
    lifecycle_logger.critical(
        "FATAL: Runtime entrypoint received non-start startup action: %s",
        action,
    )
    return False


def runtime_entrypoint(
    edition_composition: EditionComposition,
    arguments: list[str] | None = None,
) -> int | None:
    provided_args = list(sys.argv[1:] if arguments is None else arguments)
    information_exit_code = handle_information_cli_request(
        provided_args,
        program_name=sys.argv[0],
    )
    if information_exit_code is not None:
        return information_exit_code
    ensure_minimum_python_version()
    bootstrap_logger = setup_bootstrap_logger("SoAI.Bootstrap")
    lifecycle_logger = setup_bootstrap_logger("SoAI.Lifecycle")
    configure_windows_event_loop_policy()

    normalized_args = _prepare_runtime_arguments(provided_args)
    if not _validate_start_action(normalized_args, lifecycle_logger):
        return 2
    if is_windows() and not is_admin():
        lifecycle_logger.critical(
            "FATAL: The SoAI Windows backend requires administrator privileges.",
        )
        return 1

    base_dir = get_repo_root()
    config_path = resolve_config_path(base_dir)

    if not is_running_in_soai_venv(base_dir):
        bootstrap_logger.critical(
            " ".join(
                (
                    "FATAL: SoAI is not running in its managed environment.",
                    "Start it via 'soai.exe' (Windows) or 'soai.sh' (Linux/macOS).",
                ),
            ),
        )
        raise SystemExit(1)

    offline_mode_resolver = OfflineModeResolver(base_dir=base_dir)
    if offline_mode_resolver.is_offline_mode_configured():
        bootstrap_logger.info(
            "SYSTEM.RUNTIME.STAY_OFFLINE is enabled. Skipping dependency bootstrap.",
        )

    configure_resource_limits()
    load_system_prompts_catalog()

    temp_dir = resolve_temp_directory_bootstrap(base_dir, logger=bootstrap_logger)
    pid_lock = setup_pid_file_and_lock(
        base_dir,
        edition=edition_composition.capabilities.edition,
        temp_dir=temp_dir,
        logger=bootstrap_logger,
    )
    if pid_lock is None:
        bootstrap_logger.critical(
            " ".join(
                (
                    "FATAL: Could not acquire SoAI instance lock.",
                    "Another instance may still be running, or lock acquisition failed.",
                ),
            ),
        )
        raise SystemExit(1)
    release_launcher_runtime_lock_if_owned()

    application_dependencies = ApplicationDependencies(
        base_dir=base_dir,
        config_path=config_path,
        venv_path=get_venv_path(base_dir),
        version=str(__version__),
        pid_lock=pid_lock,
        bootstrap_logger=bootstrap_logger,
        lifecycle_logger=lifecycle_logger,
    )

    final_exit_code = 0
    try:
        final_exit_code = run_coroutine_in_new_event_loop(
            run_application(application_dependencies, edition_composition),
        )
    except KeyboardInterrupt:
        lifecycle_logger.info("KeyboardInterrupt received. Shutting down.")
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            lifecycle_logger,
            exception,
            message="Fatal error before main loop could start.",
            operation=OPERATION,
            level="critical",
        )
        final_exit_code = 1
    except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION)
        log_exception(
            lifecycle_logger,
            coerced,
            message="Unhandled exception before main loop could start.",
            operation=OPERATION,
            level="critical",
        )
        final_exit_code = 1
    lifecycle_logger.info(
        "--- SoAI shutdown sequence has completed. Exiting with code %s. ---",
        final_exit_code,
    )
    finalize_and_force_exit(final_exit_code, logger=bootstrap_logger)


if __name__ == "__main__":
    raise SystemExit(runtime_entrypoint(build_core_edition_composition()) or 0)
