"""SoAI - Managed bootstrap runtime directory environment [backend/core/bootstrap/runtime_directories.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass

from core.meta.paths import join_data_abs

__all__ = (
    "LOCKS_PATH_ENV",
    "PIP_CACHE_DIR_ENV",
    "PLAYWRIGHT_BROWSERS_PATH_ENV",
    "SOAI_STATE_DIR_ENV",
    "SOAI_TMP_DIR_ENV",
    "TIKTOKEN_CACHE_DIR_ENV",
    "TEMP_ENV",
    "TMPDIR_ENV",
    "TMP_ENV",
    "RuntimeDirectoryEnvironment",
    "ensure_runtime_directory_environment",
)

SOAI_STATE_DIR_ENV = "SOAI_STATE_DIR"
LOCKS_PATH_ENV = "SOAI_LOCKS_PATH"
PLAYWRIGHT_BROWSERS_PATH_ENV = "PLAYWRIGHT_BROWSERS_PATH"
SOAI_TMP_DIR_ENV = "SOAI_TMP_DIR"
TMPDIR_ENV = "TMPDIR"
TEMP_ENV = "TEMP"
TMP_ENV = "TMP"
PIP_CACHE_DIR_ENV = "PIP_CACHE_DIR"
TIKTOKEN_CACHE_DIR_ENV = "TIKTOKEN_CACHE_DIR"


@dataclass(frozen=True, slots=True)
class RuntimeDirectoryEnvironment:
    state_path: str
    locks_path: str
    playwright_browsers_path: str
    temp_path: str
    pip_cache_path: str
    tiktoken_cache_path: str


def ensure_runtime_directory_environment(repo_root_path: str) -> RuntimeDirectoryEnvironment:
    repo_root = os.path.abspath(repo_root_path)
    state_path = _resolve_directory(
        repo_root,
        SOAI_STATE_DIR_ENV,
        join_data_abs(repo_root, "state"),
    )
    locks_path = _resolve_directory(
        repo_root,
        LOCKS_PATH_ENV,
        join_data_abs(repo_root, "state", "locks"),
    )
    playwright_browsers_path = _resolve_directory(
        repo_root,
        PLAYWRIGHT_BROWSERS_PATH_ENV,
        os.path.join(state_path, "playwright-browsers"),
        zero_means_unset=True,
    )
    temp_path = _resolve_directory(
        repo_root,
        SOAI_TMP_DIR_ENV,
        os.path.join(state_path, "tmp"),
    )
    pip_cache_path = _resolve_directory(
        repo_root,
        PIP_CACHE_DIR_ENV,
        os.path.join(state_path, "pip-cache"),
    )
    tiktoken_cache_path = _resolve_directory(
        repo_root,
        TIKTOKEN_CACHE_DIR_ENV,
        os.path.join(state_path, "tiktoken-cache"),
    )
    os.environ[TMPDIR_ENV] = temp_path
    os.environ[TEMP_ENV] = temp_path
    os.environ[TMP_ENV] = temp_path
    return RuntimeDirectoryEnvironment(
        state_path=state_path,
        locks_path=locks_path,
        playwright_browsers_path=playwright_browsers_path,
        temp_path=temp_path,
        pip_cache_path=pip_cache_path,
        tiktoken_cache_path=tiktoken_cache_path,
    )


def _resolve_directory(
    repo_root_path: str,
    env_name: str,
    default_path: str,
    *,
    zero_means_unset: bool = False,
) -> str:
    configured_path = os.environ.get(env_name, "").strip()
    if configured_path and not (zero_means_unset and configured_path == "0"):
        directory_path = _absolute_configured_path(repo_root_path, configured_path)
    else:
        directory_path = os.path.abspath(default_path)
    os.makedirs(directory_path, exist_ok=True)
    os.environ[env_name] = directory_path
    return directory_path


def _absolute_configured_path(repo_root_path: str, configured_path: str) -> str:
    expanded_path = os.path.expanduser(os.path.expandvars(configured_path))
    if os.path.isabs(expanded_path):
        return os.path.abspath(expanded_path)
    return os.path.abspath(os.path.join(repo_root_path, expanded_path))
