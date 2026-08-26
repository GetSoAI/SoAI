"""SoAI - Minimal safe subprocess environment builder [backend/core/system/subprocess_env.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.platform.os import is_windows
from core.runtime.opencl_environment import OPENCL_ENV_NAMES

__all__ = (
    "WINDOWS_SUBPROCESS_ENV_NAMES",
    "build_minimal_subprocess_env",
)

SAFE_ENV_EXACT_NAMES: frozenset[str] = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "LOGNAME",
        "SHELL",
        "HOSTNAME",
        "TZ",
        "LANG",
        "TERM",
        "COLORTERM",
        "TMPDIR",
        "TEMP",
        "TMP",
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "DBUS_SESSION_BUS_ADDRESS",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
        "NODE_EXTRA_CA_CERTS",
    },
)
WINDOWS_SUBPROCESS_ENV_NAMES: frozenset[str] = frozenset(
    {
        "APPDATA",
        "COLORTERM",
        "COMSPEC",
        "CURL_CA_BUNDLE",
        "DBUS_SESSION_BUS_ADDRESS",
        "DISPLAY",
        "HOME",
        "HOMEDRIVE",
        "HOMEPATH",
        "HOSTNAME",
        "LANG",
        "LOCALAPPDATA",
        "LOGNAME",
        "NODE_EXTRA_CA_CERTS",
        "PATH",
        "PATHEXT",
        "REQUESTS_CA_BUNDLE",
        "SHELL",
        "SSL_CERT_DIR",
        "SSL_CERT_FILE",
        "SYSTEMDRIVE",
        "SYSTEMROOT",
        "TEMP",
        "TERM",
        "TMP",
        "TMPDIR",
        "TZ",
        "USERDOMAIN",
        "USERNAME",
        "USER",
        "USERPROFILE",
        "WAYLAND_DISPLAY",
        "WINDIR",
    },
)

SAFE_ENV_PREFIXES: tuple[str, ...] = (
    "LC_",
    "XDG_",
)


def _is_safe_env_name(name: str) -> bool:
    if name in SAFE_ENV_EXACT_NAMES:
        return True
    if is_windows():
        normalized_name = name.upper()
        if normalized_name in WINDOWS_SUBPROCESS_ENV_NAMES:
            return True
    if name in OPENCL_ENV_NAMES:
        return True
    for prefix in SAFE_ENV_PREFIXES:
        if name.startswith(prefix):
            return True
    return False


def build_minimal_subprocess_env(
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    result: dict[str, str] = {
        name: value for name, value in os.environ.items() if _is_safe_env_name(name)
    }
    if overrides:
        result.update(overrides)
    return result
