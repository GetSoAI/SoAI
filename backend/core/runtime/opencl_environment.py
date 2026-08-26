"""SoAI - OpenCL runtime environment normalization [backend/core/runtime/opencl_environment.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from platform import system

__all__ = (
    "OCL_ICD_VENDORS_ENV",
    "OPENCL_ENV_NAMES",
    "OPENCL_VENDOR_PATH_ENV",
    "RUSTICL_ENABLE_ENV",
    "configure_opencl_runtime_environment",
)

OPENCL_VENDOR_PATH_ENV = "OPENCL_VENDOR_PATH"
OCL_ICD_VENDORS_ENV = "OCL_ICD_VENDORS"
RUSTICL_ENABLE_ENV = "RUSTICL_ENABLE"
OPENCL_ENV_NAMES: tuple[str, ...] = (OPENCL_VENDOR_PATH_ENV, OCL_ICD_VENDORS_ENV)
RUSTICL_DEFAULT_ENABLE = "radeonsi"


def configure_opencl_runtime_environment() -> None:
    if system() != "Linux":
        return
    _configure_rusticl_default()
    if _opencl_vendor_env_is_configured():
        return
    vendors_path = _linux_system_opencl_vendors_path()
    if not _directory_has_icd_file(vendors_path):
        return
    os.environ[OPENCL_VENDOR_PATH_ENV] = vendors_path
    os.environ[OCL_ICD_VENDORS_ENV] = vendors_path


def _configure_rusticl_default() -> None:
    if os.environ.get(RUSTICL_ENABLE_ENV, "").strip():
        return
    os.environ[RUSTICL_ENABLE_ENV] = RUSTICL_DEFAULT_ENABLE


def _opencl_vendor_env_is_configured() -> bool:
    for env_name in OPENCL_ENV_NAMES:
        if os.environ.get(env_name, "").strip():
            return True
    return False


def _linux_system_opencl_vendors_path() -> str:
    return os.path.join(os.path.sep, "etc", "OpenCL", "vendors")


def _directory_has_icd_file(directory_path: str) -> bool:
    if not os.path.isdir(directory_path):
        return False
    for entry_name in os.listdir(directory_path):
        candidate_path = os.path.join(directory_path, entry_name)
        if entry_name.endswith(".icd") and os.path.isfile(candidate_path):
            return True
    return False
