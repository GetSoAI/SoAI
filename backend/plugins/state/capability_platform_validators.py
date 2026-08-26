"""SoAI - Platform validators for plugin system capability requirements [backend/plugins/state/capability_platform_validators.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.runtime.platform import (
    normalize_arch_id,
    normalize_os_id,
    normalize_platform_id,
)
from plugins.state.capability_normalization import format_capability_values
from plugins.state.capability_results import (
    CapabilityValidationResult,
    create_capability_failure,
    create_capability_success,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "validate_arch_capability",
    "validate_os_capability",
    "validate_platform_capability",
)


def validate_os_capability(
    normalized_requirement: list[str] | None,
    raw_requirement: list[str],
    host_snapshot: JSONDict,
) -> CapabilityValidationResult | None:
    if normalized_requirement is None:
        return None
    detected_os_value = str(host_snapshot.get("os") or "").strip().lower()
    detected_os = normalize_os_id(detected_os_value) or detected_os_value
    if not detected_os:
        return create_capability_failure(
            "os",
            "unknown",
            raw_requirement,
            detected_os,
            "Requires OS compatibility. Host OS is unknown.",
        )
    allowed = set(normalized_requirement)
    if "any" not in allowed and detected_os not in allowed:
        required_text = format_capability_values(raw_requirement)
        return create_capability_failure(
            "os",
            "mismatch",
            raw_requirement,
            detected_os,
            f"Requires OS compatibility ({required_text}). Detected: {detected_os.upper()}.",
        )
    return create_capability_success("os")


def validate_arch_capability(
    normalized_requirement: list[str] | None,
    raw_requirement: list[str],
    host_snapshot: JSONDict,
) -> CapabilityValidationResult | None:
    if normalized_requirement is None:
        return None
    detected_arch_value = str(host_snapshot.get("arch") or "").strip().lower()
    detected_arch = normalize_arch_id(detected_arch_value) or detected_arch_value
    if not detected_arch:
        return create_capability_failure(
            "arch",
            "unknown",
            raw_requirement,
            detected_arch,
            "Requires CPU architecture compatibility. Host architecture is unknown.",
        )
    allowed = set(normalized_requirement)
    if "any" not in allowed and detected_arch not in allowed:
        required_text = format_capability_values(raw_requirement)
        return create_capability_failure(
            "arch",
            "mismatch",
            raw_requirement,
            detected_arch,
            f"Requires CPU architecture compatibility ({required_text}). Detected: {detected_arch.upper()}.",
        )
    return create_capability_success("arch")


def validate_platform_capability(
    normalized_requirement: list[str] | None,
    raw_requirement: list[str],
    host_snapshot: JSONDict,
) -> CapabilityValidationResult | None:
    if normalized_requirement is None:
        return None
    detected_platform_value = str(host_snapshot.get("platform") or "").strip().lower()
    detected_platform = normalize_platform_id(detected_platform_value) or detected_platform_value
    if not detected_platform:
        return create_capability_failure(
            "platforms",
            "unknown",
            raw_requirement,
            detected_platform,
            "Requires platform compatibility. Host platform is unknown.",
        )
    allowed = set(normalized_requirement)
    if "any" not in allowed and detected_platform not in allowed:
        required_text = format_capability_values(raw_requirement)
        return create_capability_failure(
            "platforms",
            "mismatch",
            raw_requirement,
            detected_platform,
            f"Requires platform compatibility ({required_text}). Detected: {detected_platform.upper()}.",
        )
    return create_capability_success("platforms")
