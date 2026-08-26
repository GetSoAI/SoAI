"""SoAI - Bootstrap launcher config preparation [backend/core/bootstrap/launcher_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.bootstrap.files import read_text_file, write_text_file_atomic
from core.bootstrap.offline_mode import read_yaml_boolean_key
from core.config.file_permissions import (
    runtime_config_atomic_file_mode,
    secure_runtime_config_paths,
)
from core.meta.paths import get_config_yaml_path, join_data_abs

__all__ = (
    "atomic_copy_text_file",
    "detect_config_path",
    "ensure_config_yaml_exists",
    "is_offline_mode_enabled",
)


def detect_config_path(repo_root_path: str) -> str:
    base_path = os.path.abspath(repo_root_path)
    configured_path = os.environ.get("SOAI_CONFIG_PATH", "").strip()
    if configured_path:
        expanded = os.path.expanduser(os.path.expandvars(configured_path))
        resolved = expanded if os.path.isabs(expanded) else os.path.join(base_path, expanded)
        return os.path.abspath(os.path.normpath(resolved))
    return get_config_yaml_path(base_path)


def atomic_copy_text_file(source: str, target: str) -> None:
    target_parent = os.path.dirname(target)
    if target_parent:
        os.makedirs(target_parent, exist_ok=True)
    payload = read_text_file(source) or ""
    write_text_file_atomic(target, payload, file_mode=runtime_config_atomic_file_mode())
    secure_runtime_config_paths(target)


def ensure_config_yaml_exists(repo_root_path: str) -> None:
    config_yaml = detect_config_path(repo_root_path)
    if os.path.isfile(config_yaml):
        secure_runtime_config_paths(config_yaml, f"{config_yaml}.backup")
        return
    default_config = join_data_abs(repo_root_path, "config", "config.default.yaml")
    if not os.path.isfile(default_config):
        return
    try:
        config_dir = os.path.dirname(config_yaml)
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)
    except OSError:
        return
    atomic_copy_text_file(default_config, config_yaml)


def is_offline_mode_enabled(repo_root_path: str) -> bool:
    config_path = detect_config_path(repo_root_path)
    if not os.path.isfile(config_path):
        return False
    parsed = None
    try:
        parsed = read_yaml_boolean_key(config_path, key="SYSTEM.RUNTIME.STAY_OFFLINE")
    except (OSError, ValueError):
        parsed = None
    return bool(parsed)
