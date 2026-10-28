"""SoAI - Desktop session user resolution for elevated Linux processes [backend/core/system/desktop_session.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
import sys
from dataclasses import dataclass

from core.filesystem.open_files import open_text
from core.platform.linux_paths import linux_default_login_shell, linux_user_runtime_root
from core.platform.os import is_linux
from core.system.subprocess_env import build_minimal_subprocess_env
from core.validation.coercion import coerce_int

if sys.platform != "win32":
    import pwd

__all__ = (
    "DesktopSessionUser",
    "resolve_elevated_desktop_session_user",
)

LOGIN_UID_PATH = "/proc/self/loginuid"
UNSET_LOGIN_UID = 4294967295
SESSION_TEMPORARY_ENV_NAMES = ("TMPDIR", "TEMP", "TMP")
SESSION_RUNTIME_BOUND_ENV_NAMES = ("XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "WAYLAND_DISPLAY")


@dataclass(frozen=True, slots=True)
class DesktopSessionUser:
    user_id: int
    group_id: int
    supplementary_group_ids: tuple[int, ...]
    home_directory: str
    environment: dict[str, str]


def resolve_elevated_desktop_session_user() -> DesktopSessionUser | None:
    if not is_linux() or os.geteuid() != 0:
        return None
    user_id = _invoking_user_id()
    if user_id is None:
        return None
    try:
        account = pwd.getpwuid(user_id)
        supplementary_group_ids = tuple(os.getgrouplist(account.pw_name, account.pw_gid))
    except (KeyError, OSError):
        return None
    return DesktopSessionUser(
        user_id=account.pw_uid,
        group_id=account.pw_gid,
        supplementary_group_ids=supplementary_group_ids,
        home_directory=account.pw_dir,
        environment=_session_environment(account),
    )


def _invoking_user_id() -> int | None:
    sudo_user_id = coerce_int(os.environ.get("SUDO_UID", ""))
    if sudo_user_id is not None and 0 < sudo_user_id < UNSET_LOGIN_UID:
        return sudo_user_id
    try:
        with open_text(LOGIN_UID_PATH) as handle:
            login_user_id = coerce_int(handle.read())
    except OSError:
        return None
    if login_user_id is not None and 0 < login_user_id < UNSET_LOGIN_UID:
        return login_user_id
    return None


def _session_environment(account: pwd.struct_passwd) -> dict[str, str]:
    environment = build_minimal_subprocess_env(
        {
            "HOME": account.pw_dir,
            "USER": account.pw_name,
            "LOGNAME": account.pw_name,
            "SHELL": account.pw_shell or linux_default_login_shell(),
        }
    )
    for name in SESSION_TEMPORARY_ENV_NAMES:
        environment.pop(name, None)
    xauthority = os.environ.get("XAUTHORITY", "")
    if xauthority:
        environment["XAUTHORITY"] = xauthority
    runtime_directory = os.path.join(linux_user_runtime_root(), str(account.pw_uid))
    if environment.get("XDG_RUNTIME_DIR") != runtime_directory:
        for name in SESSION_RUNTIME_BOUND_ENV_NAMES:
            environment.pop(name, None)
        if _directory_owned_by(runtime_directory, account.pw_uid):
            environment["XDG_RUNTIME_DIR"] = runtime_directory
    return environment


def _directory_owned_by(path: str, user_id: int) -> bool:
    try:
        metadata = os.stat(path)
    except OSError:
        return False
    return metadata.st_uid == user_id and stat.S_ISDIR(metadata.st_mode)
