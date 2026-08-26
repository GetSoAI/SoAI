"""SoAI - AMD tooling availability [backend/hardware/vendors/amd/availability.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import shutil

from core.runtime.platform import get_runtime_platform

__all__ = (
    "is_amd_smi_available",
    "resolve_amd_smi_path",
)


def resolve_amd_smi_path() -> str:
    return "amd-smi"


def is_amd_smi_available() -> bool:
    runtime_platform = get_runtime_platform()
    return runtime_platform.is_linux and bool(shutil.which(resolve_amd_smi_path()))
