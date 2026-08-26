"""SoAI - File extraction terminal states [backend/core/files/extraction_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from enum import StrEnum

__all__ = ("ExtractionState",)


class ExtractionState(StrEnum):
    COMPLETE = "complete"
    DEGRADED = "degraded"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"
    TIMED_OUT = "timed_out"

    @property
    def is_usable(self) -> bool:
        return self in {ExtractionState.COMPLETE, ExtractionState.DEGRADED}
