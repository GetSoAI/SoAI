"""SoAI - Repository and backend path resolvers [backend/core/meta/paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import posixpath

from core.errors.exceptions import ValidationError

__all__ = (
    "get_backend_root",
    "get_config_yaml_path",
    "get_database_path",
    "get_project_root",
    "get_repo_root",
    "get_soai_log_path",
    "join_data_abs",
    "join_data_relative",
)

_PROJECT_ROOT_ENV_VAR = "SOAI_PROJECT_ROOT"
_PROJECT_ROOT_MARKERS: tuple[str, ...] = ("CLAUDE.md", "pyproject.toml", "README.md")
_BACKEND_DIR_NAME = "backend"


def get_backend_root() -> str:
    return os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            os.pardir,
            os.pardir,
        ),
    )


def get_repo_root() -> str:
    return os.path.dirname(get_backend_root())


def get_project_root() -> str:
    env_root = os.environ.get(_PROJECT_ROOT_ENV_VAR, "")
    if env_root:
        resolved = os.path.abspath(env_root)
        if os.path.isdir(resolved):
            return resolved
        raise ValidationError(
            f"SOAI_PROJECT_ROOT environment variable points to invalid directory: {env_root}",
        )
    current_dir = os.path.abspath(os.path.dirname(__file__))
    while True:
        if os.path.basename(current_dir) == _BACKEND_DIR_NAME:
            candidate = os.path.dirname(current_dir)
            for marker in _PROJECT_ROOT_MARKERS:
                if os.path.exists(os.path.join(candidate, marker)):
                    return candidate
            return candidate
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            break
        current_dir = parent_dir
    current_dir = os.path.abspath(os.path.dirname(__file__))
    while True:
        for marker in _PROJECT_ROOT_MARKERS:
            if os.path.exists(os.path.join(current_dir, marker)):
                return current_dir
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            break
        current_dir = parent_dir
    raise ValidationError(
        f"Unable to locate project root directory. Set {_PROJECT_ROOT_ENV_VAR} environment variable for explicit configuration.",
    )


def join_data_abs(base_dir: str, *parts: str) -> str:
    if not base_dir.strip():
        raise ValidationError("base_dir is required to resolve data path.")
    return os.path.abspath(os.path.join(base_dir, "data", *parts))


def join_data_relative(*parts: str) -> str:
    return posixpath.join("data", *parts)


def get_config_yaml_path(base_dir: str) -> str:
    return join_data_abs(base_dir, "config", "config.yaml")


def get_database_path(base_dir: str) -> str:
    return join_data_abs(base_dir, "database", "soai.db")


def get_soai_log_path(base_dir: str) -> str:
    return join_data_abs(base_dir, "logs", "soai.log")
