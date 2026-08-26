"""SoAI - Memory information gathering [backend/hardware/info_memory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import psutil

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "get_memory_info",
    "get_swap_info",
)


def get_memory_info() -> JSONDict:
    mem = psutil.virtual_memory()
    return {
        "total_bytes": mem.total,
        "used_bytes": mem.used,
        "free_bytes": mem.free,
        "total_gb": round(mem.total / 1024**3, 2),
        "used_gb": round(mem.used / 1024**3, 2),
        "free_gb": round(mem.free / 1024**3, 2),
        "percent_used": mem.percent,
    }


def get_swap_info() -> JSONDict:
    swap = psutil.swap_memory()
    return {
        "total_bytes": swap.total,
        "used_bytes": swap.used,
        "free_bytes": swap.free,
        "total_gb": round(swap.total / 1024**3, 2),
        "used_gb": round(swap.used / 1024**3, 2),
        "free_gb": round(swap.free / 1024**3, 2),
        "percent_used": swap.percent,
    }
