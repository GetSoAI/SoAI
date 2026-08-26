"""SoAI - Metrics manager runtime type guards [backend/metrics/manager/type_guards.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, TypeGuard

if TYPE_CHECKING:
    from metrics.manager.types import MetricValue

__all__ = (
    "is_float_deque",
    "is_timestamp_deque",
)


def is_float_deque(value: MetricValue) -> TypeGuard[deque[float]]:
    if not isinstance(value, deque):
        return False
    for entry in value:
        if isinstance(entry, bool) or not isinstance(entry, int | float):
            return False
    return True


def is_timestamp_deque(value: MetricValue) -> TypeGuard[deque[tuple[float, str]]]:
    if not isinstance(value, deque):
        return False
    for entry in value:
        if not isinstance(entry, tuple) or len(entry) != 2:
            return False
        ts, label = entry
        if isinstance(ts, bool) or not isinstance(ts, int | float):
            return False
        if not isinstance(label, str):
            return False
    return True
