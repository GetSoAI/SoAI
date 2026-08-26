"""SoAI - Core progress formatting utilities [backend/core/progress/formatting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math

from core.config.byte_sizes import GIB_BYTES, MIB_BYTES

__all__ = (
    "calculate_eta",
    "format_eta",
    "format_item_progress_details",
    "format_speed",
    "format_transfer_details",
    "format_transfer_log_suffix",
    "format_transfer_size",
    "format_transfer_status_message",
)


def format_speed(bytes_per_second: float) -> str:
    if bytes_per_second <= 0 or not math.isfinite(bytes_per_second):
        return ""
    if bytes_per_second >= GIB_BYTES:
        return f"{bytes_per_second / GIB_BYTES:.2f} GB/s"
    if bytes_per_second >= MIB_BYTES:
        return f"{bytes_per_second / MIB_BYTES:.2f} MB/s"
    if bytes_per_second >= 1024:
        return f"{bytes_per_second / 1024:.2f} KB/s"
    return f"{bytes_per_second:.0f} B/s"


def format_transfer_size(downloaded_size: int, total_size: int | None = None) -> str:
    downloaded = max(0, 0 if isinstance(downloaded_size, bool) else int(downloaded_size or 0))
    total = int(total_size) if total_size is not None else None
    if total is not None and total > 0:
        return f"{downloaded / MIB_BYTES:.1f}M / {total / MIB_BYTES:.1f}M"
    if downloaded > 0:
        return f"{downloaded / MIB_BYTES:.1f}M"
    return ""


def format_transfer_details(
    downloaded_size: int,
    total_size: int | None = None,
    *,
    speed: float = 0.0,
    eta_seconds: float = 0.0,
) -> str:
    size_str = format_transfer_size(downloaded_size, total_size)
    parts: list[str] = []
    if size_str:
        parts.append(size_str)
    speed_str = format_speed(speed)
    if speed_str:
        parts.append(speed_str)
    eta_str = format_eta(eta_seconds)
    if eta_str:
        parts.append(f"ETA {eta_str}")
    return " | ".join(parts)


def format_transfer_log_suffix(
    speed: float = 0.0,
    eta_seconds: float = 0.0,
    elapsed_seconds: float = 0.0,
) -> str:
    speed_str = format_speed(speed)
    eta_str = format_eta(eta_seconds)
    elapsed_str = format_eta(elapsed_seconds)
    parts: list[str] = []
    if speed_str:
        parts.append(f" @ {speed_str}")
    if eta_str:
        parts.append(f"ETA {eta_str}")
    if elapsed_str:
        parts.append(f"elapsed {elapsed_str}")
    return f" ({', '.join(parts)})" if parts else ""


def format_transfer_status_message(
    action: str,
    label: str,
    *,
    downloaded_size: int = 0,
    total_size: int | None = None,
    speed: float = 0.0,
    eta_seconds: float = 0.0,
) -> str:
    base = f"{action} {label}".strip()
    size_str = format_transfer_size(downloaded_size, total_size)
    suffix = format_transfer_log_suffix(speed, eta_seconds)
    if size_str:
        return f"{base} ({size_str}){suffix}"
    return f"{base}{suffix}"


def format_eta(seconds: float) -> str:
    if seconds <= 0 or not math.isfinite(seconds):
        return ""
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s" if secs > 0 else f"{minutes}m"
    hours = int(seconds // 3600)
    minutes = int(seconds % 3600 // 60)
    return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"


def calculate_eta(speed: float, downloaded_bytes: int, total_bytes: int) -> float:
    if speed <= 0 or total_bytes <= 0:
        return 0.0
    remaining = total_bytes - downloaded_bytes
    return remaining / speed if remaining > 0 else 0.0


def format_item_progress_details(
    items_processed: int,
    total_items: int,
    *,
    items_per_second: float = 0.0,
    eta_seconds: float = 0.0,
) -> str:
    parts: list[str] = []
    parts.append(f"{items_processed}/{total_items}")
    if items_per_second > 0:
        parts.append(f"{items_per_second:.1f}/s")
    eta_str = format_eta(eta_seconds)
    if eta_str:
        parts.append(f"ETA {eta_str}")
    return " | ".join(parts)
