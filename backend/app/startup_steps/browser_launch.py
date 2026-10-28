"""SoAI - WebUI browser launcher selection [backend/app/startup_steps/browser_launch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import platform
import shutil
import webbrowser
from typing import override

from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.system.desktop_session import DesktopSessionUser, resolve_elevated_desktop_session_user
from core.system.process_launcher import (
    DEVNULL_STREAM,
    SUBPROCESS_RECOVERABLE_EXCEPTIONS,
    spawn_background_process,
)

__all__ = (
    "BROWSER_LAUNCH_RECOVERABLE_EXCEPTIONS",
    "DesktopSessionBrowser",
    "resolve_browser_controller",
)

BROWSER_LAUNCH_RECOVERABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    RECOVERABLE_EXCEPTIONS + SUBPROCESS_RECOVERABLE_EXCEPTIONS
)
DESKTOP_OPENER_COMMAND = "xdg-open"
TEXT_MODE_BROWSER_NAMES = frozenset({"lynx", "links", "elinks", "w3m"})


class DesktopSessionBrowser(webbrowser.BaseBrowser):
    def __init__(self, executable: str, session_user: DesktopSessionUser) -> None:
        super().__init__(DESKTOP_OPENER_COMMAND)
        self.executable = executable
        self.session_user = session_user

    @override
    def open(self, url: str, new: int = 0, autoraise: bool = True) -> bool:
        home_directory = self.session_user.home_directory
        spawn_background_process(
            [self.executable, url],
            cwd=home_directory if os.path.isdir(home_directory) else None,
            env=self.session_user.environment,
            start_new_session=True,
            stdin=DEVNULL_STREAM,
            stdout=DEVNULL_STREAM,
            stderr=DEVNULL_STREAM,
            user=self.session_user.user_id,
            group=self.session_user.group_id,
            extra_groups=self.session_user.supplementary_group_ids,
        )
        return True


def resolve_browser_controller() -> tuple[webbrowser.BaseBrowser | None, str | None]:
    if platform.system() == "Linux" and (
        not (os.environ.get("DISPLAY", "") or os.environ.get("WAYLAND_DISPLAY", ""))
    ):
        return (None, "no graphical display detected")
    session_user = resolve_elevated_desktop_session_user()
    if session_user is not None:
        executable = shutil.which(
            DESKTOP_OPENER_COMMAND,
            path=session_user.environment.get("PATH", os.defpath),
        )
        if executable is None:
            return (None, f"{DESKTOP_OPENER_COMMAND} is unavailable for the desktop user")
        return (DesktopSessionBrowser(executable, session_user), None)
    try:
        controller = webbrowser.get()
    except webbrowser.Error:
        return (None, "no default browser configured")
    try:
        browser_name = controller.name
    except AttributeError:
        browser_name = ""
    if not browser_name:
        browser_name = controller.__class__.__name__
    if browser_name.lower() in TEXT_MODE_BROWSER_NAMES:
        return (None, f"text-mode browser '{browser_name}'")
    return (controller, None)
