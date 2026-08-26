"""SoAI - Epoch timestamp helpers with unit-intent types [backend/core/timing/epoch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import NewType

    EpochSeconds = NewType("EpochSeconds", int)
    EpochMillis = NewType("EpochMillis", int)
else:
    EpochSeconds = int
    EpochMillis = int

__all__ = (
    "EPOCH_MS_DETECTION_FLOOR",
    "align_epoch_ms_to_monotonic_reference",
    "epoch_ms",
    "epoch_seconds",
    "epoch_seconds_float",
)

EPOCH_MS_DETECTION_FLOOR = 946_684_800_000


def epoch_ms() -> EpochMillis:
    return EpochMillis(int(time.time() * 1000))


def epoch_seconds() -> EpochSeconds:
    return EpochSeconds(int(time.time()))


def epoch_seconds_float() -> float:
    return time.time()


def align_epoch_ms_to_monotonic_reference(
    *,
    now_epoch_ms: int,
    now_monotonic_ms: int,
    reference_monotonic_ms: int,
) -> int:
    elapsed_ms = max(0, int(now_monotonic_ms) - int(reference_monotonic_ms))
    return max(0, int(now_epoch_ms) - elapsed_ms)
