"""SoAI - PyTorch-hosted direct wheel URL resolution [backend/core/bootstrap/pytorch_wheel_urls.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import platform
import sys
import sysconfig
from dataclasses import dataclass
from urllib.parse import quote

__all__ = ("resolve_pytorch_direct_wheel_urls",)

PYTORCH_WHEEL_BASE_URL = "https://download.pytorch.org/whl"
TORCH_REQUIREMENT_PREFIX = "torch=="
TORCH_CPU_SUFFIX = "+cpu"
TRITON_REQUIREMENT_PREFIX = "triton=="


def resolve_pytorch_direct_wheel_urls(requirements_path: str) -> tuple[str, ...]:
    requirements = _read_pytorch_hosted_requirements(requirements_path)
    if requirements.torch_cpu_version is None and requirements.triton_version is None:
        return ()
    python_tag = _resolve_cpython_tag()
    if python_tag is None:
        return ()
    abi_tag = _resolve_cpython_abi_tag(python_tag)
    urls: list[str] = []
    torch_version = requirements.torch_cpu_version
    if torch_version is not None:
        torch_platform_tag = _resolve_torch_linux_platform_tag()
        if torch_platform_tag is not None:
            urls.append(
                _build_torch_cpu_url(torch_version, python_tag, abi_tag, torch_platform_tag)
            )
    triton_version = requirements.triton_version
    if triton_version is not None:
        triton_platform_tag = _resolve_triton_linux_platform_tag()
        if triton_platform_tag is not None:
            urls.append(_build_triton_url(triton_version, python_tag, abi_tag, triton_platform_tag))
    return tuple(urls)


@dataclass(frozen=True, slots=True)
class PytorchHostedRequirements:
    torch_cpu_version: str | None
    triton_version: str | None


def _read_pytorch_hosted_requirements(requirements_path: str) -> PytorchHostedRequirements:
    torch_cpu_version: str | None = None
    triton_version: str | None = None
    if not os.path.isfile(requirements_path):
        return PytorchHostedRequirements(torch_cpu_version=None, triton_version=None)
    with open(requirements_path, encoding="utf-8", errors="strict") as handle:
        for raw_line in handle:
            if torch_cpu_version is None:
                torch_cpu_version = _parse_torch_cpu_requirement_version(raw_line)
            if triton_version is None:
                triton_version = _parse_triton_requirement_version(raw_line)
    return PytorchHostedRequirements(
        torch_cpu_version=torch_cpu_version,
        triton_version=triton_version,
    )


def _parse_torch_cpu_requirement_version(raw_line: str) -> str | None:
    version = _parse_exact_requirement_version(raw_line, TORCH_REQUIREMENT_PREFIX)
    if version is None or not version.endswith(TORCH_CPU_SUFFIX):
        return None
    return version


def _parse_triton_requirement_version(raw_line: str) -> str | None:
    return _parse_exact_requirement_version(raw_line, TRITON_REQUIREMENT_PREFIX)


def _parse_exact_requirement_version(raw_line: str, requirement_prefix: str) -> str | None:
    line = raw_line.strip()
    if not line.startswith(requirement_prefix):
        return None
    requirement = line.split(";", 1)[0].strip()
    version = requirement.removeprefix(requirement_prefix).strip()
    if not version:
        return None
    return version


def _build_torch_cpu_url(
    version: str,
    python_tag: str,
    abi_tag: str,
    platform_tag: str,
) -> str:
    encoded_version = quote(version, safe=".")
    filename = f"torch-{encoded_version}-{python_tag}-{abi_tag}-{platform_tag}.whl"
    return f"{PYTORCH_WHEEL_BASE_URL}/cpu/{filename}"


def _build_triton_url(
    version: str,
    python_tag: str,
    abi_tag: str,
    platform_tag: str,
) -> str:
    filename = f"triton-{version}-{python_tag}-{abi_tag}-{platform_tag}.whl"
    return f"{PYTORCH_WHEEL_BASE_URL}/{filename}"


def _resolve_torch_linux_platform_tag() -> str | None:
    if platform.system() != "Linux":
        return None
    machine = platform.machine()
    if machine in ("x86_64", "AMD64"):
        return "manylinux_2_28_x86_64"
    if machine == "aarch64":
        return "manylinux_2_28_aarch64"
    return None


def _resolve_triton_linux_platform_tag() -> str | None:
    if platform.system() != "Linux":
        return None
    machine = platform.machine()
    if machine in ("x86_64", "AMD64"):
        return "manylinux_2_27_x86_64.manylinux_2_28_x86_64"
    return None


def _resolve_cpython_tag() -> str | None:
    if platform.python_implementation() != "CPython":
        return None
    return f"cp{sys.version_info.major}{sys.version_info.minor}"


def _resolve_cpython_abi_tag(python_tag: str) -> str:
    abi_flags = sysconfig.get_config_var("ABIFLAGS") or ""
    if "t" in abi_flags:
        return f"{python_tag}t"
    return python_tag
