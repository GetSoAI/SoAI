"""SoAI - Runtime artifact bootstrap orchestration [backend/core/bootstrap/runtime_artifacts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import platform

from core.bootstrap.command_streaming import run_bootstrap_command
from core.bootstrap.java_runtime import (
    ensure_java_runtime_installed,
    is_java_runtime_installed,
)
from core.bootstrap.launch_console import emit
from core.bootstrap.launcher_config import is_offline_mode_enabled
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
from core.bootstrap.tika_server_jar import (
    ensure_tika_server_jar_installed,
    is_tika_server_jar_installed,
)
from core.bootstrap.tiktoken_cache import (
    ensure_tiktoken_cache_installed,
    find_invalid_tiktoken_cache_assets,
)
from core.errors.exceptions import StateError

__all__ = (
    "ensure_playwright_chromium_installed",
    "ensure_runtime_artifacts_if_needed",
)


def _should_use_with_deps() -> bool:
    return False


def ensure_runtime_artifacts_if_needed(
    repo_root_path: str,
    *,
    python_executable: str,
) -> None:
    runtime_directories = ensure_runtime_directory_environment(repo_root_path)
    browsers_path = runtime_directories.playwright_browsers_path
    needs_playwright = not is_expected_chromium_installed(browsers_path=browsers_path)
    needs_java = not is_java_runtime_installed(repo_root_path)
    needs_tika_jar = not is_tika_server_jar_installed(repo_root_path)
    needs_tiktoken = bool(
        find_invalid_tiktoken_cache_assets(runtime_directories.tiktoken_cache_path),
    )
    if not needs_playwright and not needs_java and not needs_tika_jar and not needs_tiktoken:
        return
    if is_offline_mode_enabled(repo_root_path):
        missing: list[str] = []
        if needs_playwright:
            missing.append("Playwright Chromium")
        if needs_java:
            missing.append("managed Java runtime (for Tika)")
        if needs_tika_jar:
            missing.append("Apache Tika server jar")
        if needs_tiktoken:
            missing.append("tiktoken encoding cache")
        missing_text = ", ".join(missing) if missing else "runtime artifacts"
        raise StateError(
            f"SYSTEM.RUNTIME.STAY_OFFLINE is enabled but required runtime artifacts are missing or out of date: {missing_text}. Run once online to bootstrap, or disable SYSTEM.RUNTIME.STAY_OFFLINE in config.yaml.",
        )
    if needs_playwright:
        emit("INFO", "Installing Playwright Chromium runtime artifact...")
        ensure_playwright_chromium_installed(
            python_executable=python_executable,
            repo_root_path=repo_root_path,
            browsers_path=browsers_path,
        )
    if needs_java:
        emit("INFO", "Installing managed Java runtime artifact...")
        ensure_java_runtime_installed(repo_root_path)
    if needs_tika_jar:
        emit(
            "INFO",
            "Installing Apache Tika server runtime artifact. Please wait; this can take several minutes.",
        )
        ensure_tika_server_jar_installed(repo_root_path)
    if needs_tiktoken:
        emit("INFO", "Installing managed tiktoken encoding cache...")
        ensure_tiktoken_cache_installed(
            repo_root_path,
            runtime_directories.tiktoken_cache_path,
            runtime_directories.locks_path,
        )


def ensure_playwright_chromium_installed(
    *,
    python_executable: str,
    repo_root_path: str,
    browsers_path: str,
) -> None:
    if is_expected_chromium_installed(browsers_path=browsers_path):
        return
    if is_offline_mode_enabled(repo_root_path):
        raise StateError(
            "SYSTEM.RUNTIME.STAY_OFFLINE is enabled. Playwright Chromium installation is disabled.",
        )
    argv = [python_executable, "-m", "playwright", "install", "chromium"]
    if _should_use_with_deps():
        argv = [*argv[:4], "--with-deps", *argv[4:]]
    runtime_directories = ensure_runtime_directory_environment(repo_root_path)
    env = dict(os.environ)
    env[PLAYWRIGHT_BROWSERS_PATH_ENV] = browsers_path
    env[TMPDIR_ENV] = runtime_directories.temp_path
    env[PIP_CACHE_DIR_ENV] = runtime_directories.pip_cache_path
    if platform.system() == "Linux" and "DEBIAN_FRONTEND" not in env:
        env["DEBIAN_FRONTEND"] = "noninteractive"
    run_bootstrap_command(
        argv,
        log_prefix="playwright: ",
        cwd=os.path.abspath(repo_root_path),
        env=env,
    )
    prune_outcome = prune_stale_browser_directories(browsers_path=browsers_path)
    if prune_outcome.removed_directories:
        removed_text = ", ".join(prune_outcome.removed_directories)
        emit("INFO", f"Pruned stale Playwright browser directories: {removed_text}")
    if prune_outcome.failed_directories:
        failed_text = ", ".join(prune_outcome.failed_directories)
        emit("WARNING", f"Failed to prune stale Playwright browser directories: {failed_text}")
