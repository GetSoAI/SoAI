"""SoAI - SoAIBench child-local OpenCL compiler policy [backend/hardware/soaibench/opencl_child_environment.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from platform import system

from core.types.json import JSONDict

__all__ = ("configure_opencl_child_environment", "opencl_child_compiler_evidence")

RADEONSI_FORCE_FMA_ENV = "radeonsi_force_use_fma32"
MESA_SHADER_CACHE_DISABLE_ENV = "MESA_SHADER_CACHE_DISABLE"


def configure_opencl_child_environment() -> None:
    if system() != "Linux":
        return
    if RADEONSI_FORCE_FMA_ENV not in os.environ:
        os.environ[RADEONSI_FORCE_FMA_ENV] = "true"
    os.environ[MESA_SHADER_CACHE_DISABLE_ENV] = "true"


def opencl_child_compiler_evidence() -> JSONDict:
    return {
        "radeonsi_force_use_fma32": os.getenv(RADEONSI_FORCE_FMA_ENV, None),
        "mesa_shader_cache_disable": os.getenv(MESA_SHADER_CACHE_DISABLE_ENV, None),
    }
