"""SoAI - Runtime platform detection helpers [backend/core/runtime/platform.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import functools
import sys
from dataclasses import dataclass
from platform import machine, system

__all__ = (
    "RuntimePlatform",
    "get_runtime_platform",
    "normalize_arch_id",
    "normalize_os_id",
    "normalize_platform_id",
    "runtime_flags",
)


@dataclass(frozen=True, slots=True)
class RuntimePlatform:
    os_name: str
    architecture: str
    python_version: str
    is_windows: bool
    is_linux: bool
    is_macos: bool

    @property
    def os_id(self) -> str | None:
        return normalize_os_id(self.os_name)

    @property
    def architecture_id(self) -> str | None:
        return normalize_arch_id(self.architecture)

    @property
    def platform_id(self) -> str | None:
        os_id = self.os_id
        architecture_id = self.architecture_id
        if os_id is None or architecture_id is None:
            return None
        return f"{os_id}-{architecture_id}"


def normalize_os_id(value: str | None) -> str | None:
    if value is None:
        return None
    lowered = value.strip().lower()
    if not lowered:
        return None
    if lowered.startswith("linux"):
        return "linux"
    if lowered in {"darwin", "mac", "macos", "osx"}:
        return "darwin"
    if lowered in {"windows", "win", "win32", "cygwin", "msys", "nt"}:
        return "windows"
    return None


def normalize_arch_id(value: str | None) -> str | None:
    if value is None:
        return None
    lowered = value.strip().lower()
    if not lowered:
        return None
    if lowered in {"x64", "x86_64", "amd64"}:
        return "x64"
    if lowered in {"arm64", "aarch64"}:
        return "arm64"
    if lowered in {"s390", "s390x"}:
        return "s390x"
    return None


def normalize_platform_id(value: str | None) -> str | None:
    if value is None:
        return None
    os_value, separator, architecture_value = value.strip().partition("-")
    if not separator:
        return None
    os_id = normalize_os_id(os_value)
    arch_id = normalize_arch_id(architecture_value)
    if os_id is None or arch_id is None:
        return None
    return f"{os_id}-{arch_id}"


@functools.cache
def get_runtime_platform() -> RuntimePlatform:
    system_name = system()
    arch = machine() or ""
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return RuntimePlatform(
        os_name=system_name.lower(),
        architecture=arch.lower(),
        python_version=python_version,
        is_windows=system_name == "Windows",
        is_linux=system_name == "Linux",
        is_macos=system_name == "Darwin",
    )


def runtime_flags() -> dict[str, bool]:
    context = get_runtime_platform()
    return {
        "windows": context.is_windows,
        "linux": context.is_linux,
        "macos": context.is_macos,
    }
