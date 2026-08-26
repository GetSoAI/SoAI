"""SoAI - Updater base path normalization [backend/app/updater/path_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.logging.protocols import LoggerProtocol

__all__ = (
    "normalize_base_path",
    "resolve_main_py_path",
)


def resolve_main_py_path(base_path: str, entrypoint_relative_path: str) -> str:
    return os.path.join(base_path, *entrypoint_relative_path.split("/"))


def normalize_base_path(base_path: str, *, logger: LoggerProtocol) -> str | None:
    try:
        resolved_base = os.path.abspath(base_path)
    except (TypeError, ValueError):
        logger.error("Invalid SYSTEM.PATHS.BASE in configuration.")
        return None
    if not resolved_base or os.path.dirname(resolved_base) == resolved_base:
        logger.error("Refusing to operate on an unsafe SYSTEM.PATHS.BASE: %s", resolved_base)
        return None
    if not os.path.isdir(resolved_base):
        logger.error("SYSTEM.PATHS.BASE does not exist or is not a directory: %s", resolved_base)
        return None
    return resolved_base
