"""SoAI - GPU display-name selection between PCI and vendor telemetry [backend/hardware/gpu_inventory/display_name.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("select_gpu_display_name",)

GENERIC_PLACEHOLDER_NAMES: frozenset[str] = frozenset(
    {
        "",
        "gpu",
        "device",
        "graphics",
        "graphics device",
        "display",
        "display controller",
        "vga compatible controller",
        "unknown",
        "amd gpu",
        "nvidia gpu",
        "intel gpu",
    },
)


def select_gpu_display_name(baseline_name: JSONValue, telemetry_name: JSONValue) -> str | None:
    baseline = _clean(baseline_name)
    telemetry = _clean(telemetry_name)
    if _is_product_name(telemetry):
        return telemetry
    if _is_product_name(baseline):
        return baseline
    return telemetry or baseline


def _clean(value: JSONValue) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _is_product_name(value: str | None) -> bool:
    if value is None:
        return False
    normalized = " ".join(value.split()).lower()
    if normalized in GENERIC_PLACEHOLDER_NAMES:
        return False
    return any(character.isspace() for character in value.strip())
