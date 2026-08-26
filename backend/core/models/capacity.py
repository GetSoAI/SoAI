"""SoAI - Model capacity evaluation utilities [backend/core/models/capacity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("evaluate_variant_capacity",)


def evaluate_variant_capacity(
    variant: JSONDict,
    available_vram_gb: float | None,
    available_disk_bytes: int | None,
    available_total_memory_gb: float | None,
) -> tuple[bool | None, bool | None, bool | None, str]:

    def _format_capacity(value: float | None) -> str | None:
        if value is None:
            return None
        try:
            return f"{round(float(value), 2)}"
        except (TypeError, ValueError):
            return None

    size_bytes = variant.get("size_bytes")
    total_memory_required = variant.get("ram_required_gb")
    vram_required = variant.get("vram_required_gb")
    total_memory_required = (
        total_memory_required if isinstance(total_memory_required, int | float) else None
    )
    vram_required = vram_required if isinstance(vram_required, int | float) else None
    total_memory_fit: bool | None = None
    effective_vram_required = (
        vram_required if isinstance(vram_required, int | float) else total_memory_required
    )
    disk_fit: bool | None = None
    if available_disk_bytes is not None and isinstance(size_bytes, int | float):
        try:
            disk_fit = available_disk_bytes >= int(size_bytes)
        except (TypeError, ValueError, OverflowError):
            disk_fit = None
    vram_fit: bool | None = None
    if available_vram_gb is not None and isinstance(effective_vram_required, int | float):
        try:
            vram_fit = available_vram_gb >= float(effective_vram_required)
        except (TypeError, ValueError):
            vram_fit = None
    if available_total_memory_gb is not None and total_memory_required is not None:
        try:
            total_memory_fit = available_total_memory_gb >= float(total_memory_required)
        except (TypeError, ValueError):
            total_memory_fit = None
    size_gb_value: float | None = None
    raw_size_gb = variant.get("size_gb")
    if isinstance(raw_size_gb, int | float):
        size_gb_value = float(raw_size_gb)
    elif isinstance(size_bytes, int | float):
        try:
            size_gb_value = float(size_bytes) / 1024**3
        except (TypeError, ValueError, OverflowError):
            size_gb_value = None
    requirement_statements: list[str] = []
    if size_gb_value is not None:
        formatted_download = _format_capacity(size_gb_value)
        if formatted_download:
            requirement_statements.append(f"Download size: {formatted_download} GB")
    if isinstance(total_memory_required, int | float):
        formatted_total = _format_capacity(total_memory_required)
        if formatted_total:
            requirement_statements.append(f"Total memory required: {formatted_total} GB")
    if isinstance(vram_required, int | float):
        formatted_vram = _format_capacity(vram_required)
        if formatted_vram:
            requirement_statements.append(f"VRAM required: {formatted_vram} GB")
    requirement_text = (
        "; ".join(requirement_statements) if requirement_statements else "Sizing data unavailable"
    )
    requirement_sentence = (
        requirement_text if requirement_text.endswith(".") else f"{requirement_text}."
    )
    if (
        disk_fit is True
        and vram_fit is True
        and (total_memory_fit is True or total_memory_fit is None)
    ):
        return (
            disk_fit,
            vram_fit,
            total_memory_fit,
            f"{requirement_sentence} All requirements are within your system's detected capacity.",
        )
    availability_descriptors: list[str] = []
    if disk_fit is False:
        disk_free_descriptor = None
        if available_disk_bytes is not None:
            disk_free_descriptor = _format_capacity(available_disk_bytes / 1024**3)
        issue = "Disk capacity"
        if disk_free_descriptor:
            issue = f"Disk capacity {disk_free_descriptor} GB free"
        availability_descriptors.append(issue)
    if vram_fit is False:
        available_vram_descriptor = _format_capacity(available_vram_gb)
        issue = "VRAM capacity"
        if available_vram_descriptor:
            issue = f"VRAM capacity {available_vram_descriptor} GB available"
        availability_descriptors.append(issue)
    if total_memory_fit is False:
        available_total_descriptor = _format_capacity(available_total_memory_gb)
        issue = "Combined memory capacity"
        if available_total_descriptor:
            issue = f"Combined memory capacity {available_total_descriptor} GB available"
        availability_descriptors.append(issue)
    if availability_descriptors:
        limitation_sentence = "; ".join(availability_descriptors)
        return (
            disk_fit,
            vram_fit,
            total_memory_fit,
            f"{requirement_sentence} Does not fit: {limitation_sentence}.",
        )
    return (
        disk_fit,
        vram_fit,
        total_memory_fit,
        f"{requirement_sentence} Capacity information unavailable.",
    )
