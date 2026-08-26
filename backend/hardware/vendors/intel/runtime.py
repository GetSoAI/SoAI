"""SoAI - Intel runtime binary resolution [backend/hardware/vendors/intel/runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import shutil

from core.runtime.platform import get_runtime_platform

__all__ = (
    "is_xpu_smi_available",
    "resolve_xpu_smi_path",
)


def resolve_xpu_smi_path() -> str:
    runtime_platform = get_runtime_platform()
    return "xpu-smi.exe" if runtime_platform.is_windows else "xpu-smi"


def is_xpu_smi_available() -> bool:
    return bool(shutil.which(resolve_xpu_smi_path()))
