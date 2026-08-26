"""SoAI - NVIDIA settings control readiness detection [backend/hardware/vendors/nvidia/settings_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING

from core.system.commands import run_argv_capture
from hardware.vendors.nvidia.paths import nvidia_xorg_config_path

if TYPE_CHECKING:
    from core.runtime.platform import RuntimePlatform

__all__ = ("detect_nvidia_settings_available",)


def _has_display_environment() -> bool:
    display_value = os.environ.get("DISPLAY", "")
    return isinstance(display_value, str) and bool(display_value.strip())


def _has_running_xorg() -> bool:
    try:
        result = run_argv_capture(["pgrep", "-a", "Xorg"], timeout=5)
    except (OSError, RuntimeError, ValueError):
        return False
    return result.return_code == 0 and bool(result.stdout.strip())


def detect_nvidia_settings_available(runtime_platform: RuntimePlatform) -> tuple[bool, str | None]:
    if not runtime_platform.is_linux:
        return (False, None)
    if shutil.which("nvidia-settings") is None:
        return (False, "nvidia-settings not found in PATH")
    if _has_display_environment():
        return (True, None)
    if _has_running_xorg():
        return (True, None)
    if shutil.which("Xorg") is None:
        return (False, "Xorg not found for headless nvidia-settings")
    if not os.path.exists(nvidia_xorg_config_path()):
        return (False, "xorg.conf not found for headless nvidia-settings")
    return (True, None)
