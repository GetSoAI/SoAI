"""SoAI - Progress bar formatting for terminal output [backend/core/progress/progress_bar.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math

from core.progress.percent import clamp_percent

__all__ = ("format_progress_bar",)


def format_progress_bar(
    percent: int,
    downloaded_mb: float | None = None,
    total_mb: float | None = None,
) -> str:
    percent_int = 0
    try:
        percent_int = int(percent)
    except (TypeError, ValueError):
        percent_int = 0
    percent_int = clamp_percent(percent_int)
    filled = percent_int // 4
    progress_bar = "#" * filled + "-" * (25 - filled)
    size_str = ""
    if downloaded_mb is not None and total_mb is not None:
        try:
            downloaded_val = float(downloaded_mb)
            total_val = float(total_mb)
            if math.isfinite(downloaded_val) and math.isfinite(total_val) and (total_val > 0):
                total_fmt = f"{total_val:.1f}"
                downloaded_fmt = f"{downloaded_val:.1f}".rjust(len(total_fmt))
                size_str = f" ({downloaded_fmt}M/{total_fmt}M)"
        except (TypeError, ValueError):
            size_str = ""
    return f"[{progress_bar}] {percent_int:3d}%{size_str}"
