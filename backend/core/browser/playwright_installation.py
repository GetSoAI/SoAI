"""SoAI - Playwright Chromium installation helpers [backend/core/browser/playwright_installation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys
import time

from core.bootstrap.playwright_browser_state import (
    is_expected_chromium_installed,
    prune_stale_browser_directories,
)
from core.bootstrap.runtime_directories import (
    PIP_CACHE_DIR_ENV,
    PLAYWRIGHT_BROWSERS_PATH_ENV,
    TMPDIR_ENV,
    ensure_runtime_directory_environment,
)
from core.concurrency.bounded_blocking import (
    BoundedBlockingPool,
    BoundedBlockingTimeoutBase,
    create_bounded_thread_pool,
    run_bounded_blocking_call,
)
from core.concurrency.bounded_pool_lifecycle import (
    resolve_lazy_bounded_pool,
    shutdown_lazy_bounded_pool,
)
from core.errors.exceptions import ProcessError
from core.files.locking import guarded_file_lock
from core.logging.trace import get_logger
from core.system.commands import run_argv_capture
from core.validation.integers import is_strict_int

__all__ = (
    "install_chromium",
    "install_chromium_async",
    "should_retry_install_after_launch_error",
    "shutdown_playwright_install_executor",
)

LOGGER_NAME = "SoAI.core.browser.playwright_installation"

_PLAYWRIGHT_INSTALL_EXECUTOR_WORKERS: int = 1


class _PlaywrightInstallExecutorState:
    executor: BoundedBlockingPool | None = None


def _build_playwright_install_command(*, python_executable: str) -> list[str]:
    return [python_executable, "-m", "playwright", "install", "chromium"]


def _should_use_with_deps() -> bool:
    return False


def should_retry_install_after_launch_error(exception: Exception) -> bool:
    message = str(exception)
    lowered = message.lower()
    return "executable doesn't exist" in lowered or "playwright install" in lowered


def _compute_chromium_install_lock_path(*, browsers_path: str) -> str:
    if not isinstance(browsers_path, str) or not browsers_path.strip():
        raise ProcessError(
            "browsers_path must be a non-empty string",
            operation="core.browser.playwright_installation.compute_chromium_install_lock_path",
        )
    return os.path.join(os.path.abspath(browsers_path), "chromium.install.lock")


def install_chromium(
    *,
    python_executable: str,
    repo_root_path: str,
    timeout_sec: int,
    force: bool = False,
) -> None:
    if not isinstance(python_executable, str) or not python_executable.strip():
        raise ProcessError(
            "python_executable must be a non-empty string",
            operation="core.browser.playwright_installation.install_chromium",
        )
    if not is_strict_int(timeout_sec) or timeout_sec < 1:
        raise ProcessError(
            "timeout_sec must be an integer >= 1",
            operation="core.browser.playwright_installation.install_chromium",
        )
    if not isinstance(repo_root_path, str) or not repo_root_path.strip():
        raise ProcessError(
            "repo_root_path must be a non-empty string",
            operation="core.browser.playwright_installation.install_chromium",
        )

    runtime_directories = ensure_runtime_directory_environment(repo_root_path)
    browsers_path = runtime_directories.playwright_browsers_path
    lock_path = _compute_chromium_install_lock_path(browsers_path=browsers_path)

    start_monotonic = time.monotonic()
    with guarded_file_lock(
        lock_path,
        timeout=float(timeout_sec),
        on_timeout=ProcessError(
            f"Timed out waiting for Chromium install lock after {timeout_sec}s",
            operation="core.browser.playwright_installation.install_chromium.lock_timeout",
            details={"lock_path": lock_path, "timeout_sec": timeout_sec},
        ),
    ):
        if not force and is_expected_chromium_installed(browsers_path=browsers_path):
            return

        remaining_timeout_sec = max(
            1,
            int(float(timeout_sec) - (time.monotonic() - start_monotonic)),
        )

        argv = _build_playwright_install_command(python_executable=python_executable)
        if _should_use_with_deps():
            argv = [*argv[:4], "--with-deps", *argv[4:]]

        env = dict(os.environ)
        env[PLAYWRIGHT_BROWSERS_PATH_ENV] = browsers_path
        env[TMPDIR_ENV] = runtime_directories.temp_path
        env[PIP_CACHE_DIR_ENV] = runtime_directories.pip_cache_path
        if sys.platform.startswith("linux"):
            if "DEBIAN_FRONTEND" not in env:
                env["DEBIAN_FRONTEND"] = "noninteractive"

        result = run_argv_capture(
            argv,
            timeout=remaining_timeout_sec,
            env=env,
            cwd=os.path.abspath(repo_root_path),
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.return_code != 0:
            raise ProcessError(
                f"Playwright Chromium install failed with code {result.return_code}",
                operation="core.browser.playwright_installation.install_chromium",
                details={
                    "argv": argv,
                    "browsers_path": browsers_path,
                    "stdout": (result.stdout or "").strip(),
                    "stderr": (result.stderr or "").strip(),
                },
            )
        prune_outcome = prune_stale_browser_directories(browsers_path=browsers_path)
        logger = get_logger(LOGGER_NAME)
        if prune_outcome.removed_directories:
            logger.info(
                "Pruned stale Playwright browser directories: %s",
                ", ".join(prune_outcome.removed_directories),
            )
        if prune_outcome.failed_directories:
            logger.warning(
                "Failed to prune stale Playwright browser directories: %s",
                ", ".join(prune_outcome.failed_directories),
            )


def _create_playwright_install_executor() -> BoundedBlockingPool:
    return create_bounded_thread_pool(
        label="playwright_install",
        max_workers=_PLAYWRIGHT_INSTALL_EXECUTOR_WORKERS,
        max_in_flight=_PLAYWRIGHT_INSTALL_EXECUTOR_WORKERS,
        thread_name_prefix="soai-pw-install",
    )


def _get_playwright_install_executor() -> BoundedBlockingPool:
    executor = resolve_lazy_bounded_pool(
        _PlaywrightInstallExecutorState.executor,
        _create_playwright_install_executor,
    )
    _PlaywrightInstallExecutorState.executor = executor
    return executor


async def install_chromium_async(
    *,
    python_executable: str,
    repo_root_path: str,
    timeout_sec: int,
    force: bool = False,
) -> None:
    def _blocking_install() -> None:
        install_chromium(
            python_executable=python_executable,
            repo_root_path=repo_root_path,
            timeout_sec=timeout_sec,
            force=force,
        )

    try:
        outer_timeout_sec = float(timeout_sec) + 5.0
        await run_bounded_blocking_call(
            _get_playwright_install_executor(),
            _blocking_install,
            timeout_sec=outer_timeout_sec,
        )
    except BoundedBlockingTimeoutBase as exception:
        exception.cancel_future()
        raise ProcessError(
            f"Playwright Chromium install timed out after {timeout_sec}s",
            operation="core.browser.playwright_installation.install_chromium_async",
            details={"timeout_sec": timeout_sec},
        ) from exception


def shutdown_playwright_install_executor() -> None:
    executor = _PlaywrightInstallExecutorState.executor
    shutdown_lazy_bounded_pool(executor)
    _PlaywrightInstallExecutorState.executor = None
