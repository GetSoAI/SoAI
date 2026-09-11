"""SoAI - Target update runtime dependency and migration-hook preparation [backend/app/updater/target_runtime_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from subprocess import CalledProcessError

from app.edition_composition import UpdaterComposition
from core.bootstrap.python_dependencies import bootstrap_python_dependencies_if_needed
from core.bootstrap.venv_paths import get_venv_path, get_venv_python_executable
from core.config.numeric import coerce_int_or_none
from core.config.protocols import ConfigProtocol
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.system.commands import run_argv_capture

__all__ = ("prepare_target_update_runtime",)

OPERATION_APPLICATION_UPDATER_POST_UPDATE_HOOK = "application_updater.post_update_hook"
OPERATION_PREPARE_DEPENDENCIES = "application_updater.prepare_dependencies"
DEPENDENCY_PREPARATION_EXCEPTIONS: tuple[type[Exception], ...] = (
    OSError,
    CalledProcessError,
    StateError,
    ValidationError,
    *RECOVERABLE_EXCEPTIONS,
)


def prepare_target_update_runtime(
    *,
    base_path: str,
    config_path: str,
    config: ConfigProtocol,
    updater: UpdaterComposition,
    logger: LoggerProtocol,
) -> bool:
    runtime_python = get_venv_python_executable(get_venv_path(base_path))
    try:
        bootstrap_python_dependencies_if_needed(
            base_path,
            python_executable=runtime_python,
            offline_mode=config.get_bool("SYSTEM.RUNTIME.STAY_OFFLINE"),
        )
    except DEPENDENCY_PREPARATION_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Target dependency preparation failed.",
            operation=OPERATION_PREPARE_DEPENDENCIES,
            level="error",
        )
        return False
    hook_module = updater.post_update_hook_module
    hook_script = os.path.join(
        base_path,
        updater.post_update_hook_relative_path,
    )
    if os.path.exists(hook_script):
        logger.info("Executing post-update hook script...")
        hook_timeout = _resolve_post_update_hook_timeout_seconds(config, logger=logger)
        if hook_timeout is None:
            return False
        try:
            pythonpath = os.pathsep.join((os.path.join(base_path, "backend"), base_path))
            env = dict(os.environ)
            env["SOAI_CONFIG_PATH"] = config_path
            existing_pythonpath = env.get("PYTHONPATH")
            env["PYTHONPATH"] = (
                f"{pythonpath}{os.pathsep}{existing_pythonpath}"
                if existing_pythonpath
                else pythonpath
            )
            result = run_argv_capture(
                [runtime_python, "-P", "-m", hook_module],
                cwd=base_path,
                timeout=hook_timeout,
                check=True,
                env=env,
            )
            logger.info("Post-update hook finished successfully:\n%s", result.stdout)
        except CalledProcessError as exception:
            log_handled_exception(
                logger,
                exception,
                message="Post-update hook failed.",
                operation=OPERATION_APPLICATION_UPDATER_POST_UPDATE_HOOK,
                details={
                    "returncode": exception.returncode,
                    "stdout": str(exception.output or "").strip(),
                    "stderr": str(exception.stderr or "").strip(),
                },
                level="error",
            )
            return False
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Post-update hook failed.",
                operation=OPERATION_APPLICATION_UPDATER_POST_UPDATE_HOOK,
                level="error",
            )
            return False
    return True


def _resolve_post_update_hook_timeout_seconds(
    config: ConfigProtocol,
    *,
    logger: LoggerProtocol,
) -> int | None:
    raw = config.get("SYSTEM.UPDATER.POST_UPDATE_HOOK_TIMEOUT_SEC", 7200)
    if raw is None:
        return 7200
    return coerce_int_or_none(
        raw,
        minimum=1,
        invalid_message="SYSTEM.UPDATER.POST_UPDATE_HOOK_TIMEOUT_SEC must be a positive integer.",
        below_minimum_message="SYSTEM.UPDATER.POST_UPDATE_HOOK_TIMEOUT_SEC must be greater than 0.",
        logger=logger,
    )
