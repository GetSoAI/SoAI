"""SoAI - Runtime configuration file permission enforcement [backend/core/config/file_permissions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat

__all__ = (
    "RUNTIME_CONFIG_FILE_MODE",
    "runtime_config_atomic_file_mode",
    "secure_runtime_config_file_permissions",
    "secure_runtime_config_paths",
)

RUNTIME_CONFIG_FILE_MODE = 0o600


def runtime_config_atomic_file_mode() -> int | None:
    if os.name == "nt":
        return None
    return RUNTIME_CONFIG_FILE_MODE


def secure_runtime_config_file_permissions(path: str) -> None:
    if os.name == "nt":
        return
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return
    try:
        status = os.fstat(descriptor)
        if not stat.S_ISREG(status.st_mode):
            raise OSError(f"Runtime configuration path is not a regular file: {path}")
        os.fchmod(descriptor, RUNTIME_CONFIG_FILE_MODE)
    finally:
        os.close(descriptor)


def secure_runtime_config_paths(*paths: str | None) -> None:
    for path in paths:
        if path is not None:
            secure_runtime_config_file_permissions(path)
