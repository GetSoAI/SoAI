"""SoAI - OHLC gap-fill entry helpers [backend/core/metrics/ohlc_gap_fill.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.types.json import JSONDict

__all__ = ("build_gap_fill_entry",)


def build_gap_fill_entry(last_close: float | None) -> JSONDict | None:
    if last_close is None:
        return None
    return {
        "open": last_close,
        "high": last_close,
        "low": last_close,
        "close": last_close,
        "avg": last_close,
        "count": 0,
        "gap_fill": True,
        "interpolated": True,
    }
