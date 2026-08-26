"""SoAI - Backend variant platform label helpers [backend/core/plugins/backend_variant_platforms.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence

from core.runtime.platform import (
    get_runtime_platform,
    normalize_arch_id,
    normalize_os_id,
    normalize_platform_id,
)
from core.types.json import JSONValue
from core.validation.strings import coerce_optional_trimmed_str

__all__ = (
    "current_backend_variant_arch",
    "current_backend_variant_os",
    "current_backend_variant_platform",
    "format_backend_variant_platform_label",
    "normalize_backend_variant_supported_arch",
    "normalize_backend_variant_supported_os",
    "normalize_backend_variant_supported_platforms",
    "supported_platforms_to_os",
)


def current_backend_variant_os() -> str:
    runtime_platform = get_runtime_platform()
    return runtime_platform.os_id or runtime_platform.os_name


def current_backend_variant_arch() -> str:
    runtime_platform = get_runtime_platform()
    return runtime_platform.architecture_id or runtime_platform.architecture


def current_backend_variant_platform() -> str:
    return f"{current_backend_variant_os()}-{current_backend_variant_arch()}"


def normalize_backend_variant_supported_os(value: JSONValue) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        os_id = _normalize_os_id(item)
        if os_id is None or os_id in seen:
            continue
        seen.add(os_id)
        normalized.append(os_id)
    return normalized


def normalize_backend_variant_supported_platforms(value: JSONValue) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        platform_id = _normalize_platform_id(item)
        if platform_id is None or platform_id in seen:
            continue
        seen.add(platform_id)
        normalized.append(platform_id)
    return normalized


def normalize_backend_variant_supported_arch(value: JSONValue) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        arch_id = _normalize_arch_id(item)
        if arch_id is None or arch_id in seen:
            continue
        seen.add(arch_id)
        normalized.append(arch_id)
    return normalized


def format_backend_variant_platform_label(supported_os: list[str]) -> str:
    labels = [_backend_variant_os_label(os_id) for os_id in supported_os]
    return " / ".join(labels)


def supported_platforms_to_os(supported_platforms: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for platform_id in supported_platforms:
        os_id = platform_id.split("-", 1)[0]
        if os_id in seen:
            continue
        seen.add(os_id)
        normalized.append(os_id)
    return normalized


def _normalize_os_id(value: JSONValue) -> str | None:
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None:
        return None
    return normalize_os_id(normalized)


def _backend_variant_os_label(os_id: str) -> str:
    if os_id == "linux":
        return "Linux"
    if os_id == "darwin":
        return "Mac OS"
    if os_id == "windows":
        return "Windows"
    return os_id.upper()


def _normalize_arch_id(value: JSONValue) -> str | None:
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None:
        return None
    arch_id = normalize_arch_id(normalized)
    if arch_id is not None:
        return arch_id
    return None


def _normalize_platform_id(value: JSONValue) -> str | None:
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None:
        return None
    return normalize_platform_id(normalized)
