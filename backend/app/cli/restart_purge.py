"""SoAI - Restart purge sentinel handling for CLI startup [backend/app/cli/restart_purge.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import os
import subprocess
import sys

from app.cli.windows_console_service import (
    WindowsConsoleService,
    WindowsConsoleServiceDependencies,
)
from app.purger.executor import launch_detached_purger
from core.bootstrap.runtime_directories import ensure_runtime_directory_environment
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, StateError
from core.files.locking import guarded_file_lock
from core.platform.os import is_windows
from core.restart_purge.transaction import (
    complete_committed_restart_purge_cleanup,
    load_restart_purge_transaction,
)
from core.runtime.process_identity import SOAI_BACKEND_MAIN_SUBPATH
from core.system.process_launcher import spawn_background_process
from core.system.process_replacement import (
    flush_process_replacement_output,
    replace_current_process,
)

__all__ = ("handle_restart_purge_sentinel",)

OPERATION = "main.perform_restart_purge"
PURGER_LOCK_SUFFIX = ".worker.lock"


def handle_restart_purge_sentinel(
    base_dir: str,
    *,
    sentinel_path: str,
    manifest_path: str,
    logger: logging.Logger,
) -> None:
    sentinel_exists = os.path.lexists(sentinel_path)
    manifest_exists = os.path.lexists(manifest_path)
    if not sentinel_exists and not manifest_exists:
        return
    logger.warning(
        "RESTART PURGE SENTINEL DETECTED. Waiting for detached purger to complete cleanup.",
    )
    try:
        with guarded_file_lock(
            f"{sentinel_path}{PURGER_LOCK_SUFFIX}",
            timeout=0,
            on_timeout=StateError("Another process is already recovering the restart purge."),
        ):
            committed_cleanup = complete_committed_restart_purge_cleanup(
                sentinel_path=sentinel_path,
                manifest_path=manifest_path,
            )
            if not committed_cleanup:
                load_restart_purge_transaction(
                    sentinel_path=sentinel_path,
                    manifest_path=manifest_path,
                )
                purger = launch_detached_purger(
                    base_dir,
                    sentinel_path,
                    manifest_path,
                )
                try:
                    return_code = purger.wait(timeout=60.0)
                except subprocess.TimeoutExpired as exception:
                    purger.terminate()
                    try:
                        purger.wait(timeout=5.0)
                    except subprocess.TimeoutExpired:
                        purger.kill()
                        purger.wait(timeout=5.0)
                    raise SystemExit(1) from exception
                if (
                    return_code != 0
                    or os.path.lexists(sentinel_path)
                    or os.path.lexists(manifest_path)
                ):
                    logger.critical(
                        "Restart purge did not commit. Recovery evidence was retained for retry.",
                    )
                    raise SystemExit(1)
            logger.info(
                "Restart purge cleanup complete. Relaunching application for a clean start."
            )
            ensure_runtime_directory_environment(base_dir)
            flush_process_replacement_output()
            main_script_path = os.path.abspath(os.path.join(base_dir, SOAI_BACKEND_MAIN_SUBPATH))
            relaunch_cmd = [sys.executable, main_script_path, *sys.argv[1:]]
            if is_windows():
                flags = WindowsConsoleService(
                    WindowsConsoleServiceDependencies(logger=logger),
                ).get_subprocess_flags()
                spawn_background_process(
                    relaunch_cmd,
                    creationflags=flags,
                    env=os.environ.copy(),
                )
                raise SystemExit(0)
            raise SystemExit(replace_current_process(relaunch_cmd))
    except (SoAIError, TimeoutError, subprocess.SubprocessError) as exception:
        log_exception(
            logger,
            exception,
            message="FATAL: An unhandled error occurred during the restart purge process",
            operation=OPERATION,
            level="critical",
        )
        logger.critical("Restart purge recovery evidence was retained for the next retry.")
        raise SystemExit(1) from exception
