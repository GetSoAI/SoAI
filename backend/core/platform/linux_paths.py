"""SoAI - Shared Linux filesystem path resolvers [backend/core/platform/linux_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from os import sep

__all__ = (
    "linux_default_home_root",
    "linux_default_login_shell",
    "linux_user_runtime_root",
    "soai_mount_base_path",
)


def linux_default_home_root() -> str:
    return f"{sep}home"


def linux_default_login_shell() -> str:
    return f"{sep}bin{sep}bash"


def linux_user_runtime_root() -> str:
    return f"{sep}run{sep}user"


def soai_mount_base_path() -> str:
    return f"{sep}mnt{sep}soai"
