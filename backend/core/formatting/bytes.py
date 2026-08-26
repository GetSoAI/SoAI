"""SoAI - General human-readable byte and rate formatting [backend/core/formatting/bytes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.config.byte_sizes import GIB_BYTES, MIB_BYTES

__all__ = (
    "format_bytes",
    "format_bytes_gb_fixed",
    "format_bytes_mb_fixed",
    "format_bytes_per_second",
)

_BYTE_RATE_PREFIXES: tuple[str, ...] = ("", "K", "M", "G", "T")


def format_bytes(size_bytes: float) -> str:
    value = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024.0:
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{value:.2f} PB"


def format_bytes_mb_fixed(size_bytes: int) -> str:
    return f"{size_bytes / MIB_BYTES:.0f} MB"


def format_bytes_gb_fixed(size_bytes: int) -> str:
    return f"{size_bytes / GIB_BYTES:.0f} GB"


def format_bytes_per_second(byte_count: float | None) -> str:
    if byte_count is None:
        return "N/A"
    value = float(byte_count)
    power, power_index = 1024, 0
    while value >= power and power_index < len(_BYTE_RATE_PREFIXES) - 1:
        value /= power
        power_index += 1
    return f"{value:.2f} {_BYTE_RATE_PREFIXES[power_index]}B/s"
