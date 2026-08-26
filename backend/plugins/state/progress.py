"""SoAI - Plugin task progress helpers [backend/plugins/state/progress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from core.progress.percent import (
    coerce_strict_text_percent_or_default,
    scale_percent_range,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

    type PhaseType = Literal["setup", "download", "finalize"]

__all__ = ("PhaseAwareProgressMapper",)


class PhaseAwareProgressMapper:
    __slots__ = ("_current_percent", "_current_phase", "_phase_ranges")

    def __init__(
        self,
        *,
        phase_ranges: dict[PhaseType, tuple[int, int]] | None = None,
    ) -> None:
        self._current_phase: PhaseType = "setup"
        self._current_percent = 0
        if phase_ranges is None:
            self._phase_ranges: dict[PhaseType, tuple[int, int]] = {
                "setup": (0, 15),
                "download": (15, 85),
                "finalize": (85, 100),
            }
        else:
            self._phase_ranges = phase_ranges

    def process_callback(self, data: JSONDict) -> int:
        data_type = data.get("type")
        raw_percent = data.get("percent")
        if data_type == "progress" and self._current_phase == "setup":
            self._current_phase = "download"
        elif data_type == "log" and self._current_phase == "download" and raw_percent is None:
            download_range_end = self._phase_ranges["download"][1]
            if self._current_percent >= download_range_end:
                self._current_phase = "finalize"
        if data_type == "progress" and raw_percent is not None:
            mapped = self._map_to_phase_range(raw_percent, self._current_phase)
        else:
            mapped = self._auto_advance_in_phase()
        self._current_percent = max(self._current_percent, mapped)
        return self._current_percent

    def _map_to_phase_range(self, plugin_percent: JSONValue, phase: PhaseType) -> int:
        start, end = self._phase_ranges[phase]
        clamped = coerce_strict_text_percent_or_default(plugin_percent, default=0)
        return scale_percent_range(value=clamped, start_percent=start, end_percent=end)

    def _auto_advance_in_phase(self) -> int:
        start, end = self._phase_ranges[self._current_phase]
        step = max(1, int((end - start) / 10))
        return min(end - 1, self._current_percent + step)
