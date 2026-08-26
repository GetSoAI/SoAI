"""SoAI - Startup timings recorder for coarse-grained performance attribution [backend/core/timing/startup_timings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field

from core.serialization.json import serialize_json_compact_stable
from core.timing.monotonic import monotonic_ms

__all__ = ("StartupTimingsRecorder",)


@dataclass(slots=True)
class StartupTimingsRecorder:
    start_ms: int = field(default_factory=monotonic_ms)
    _durations_ms: dict[str, int] = field(default_factory=dict[str, int])

    def record_duration_ms(self, name: str, duration_ms: int) -> None:
        normalized_name = str(name or "").strip()
        if not normalized_name:
            return
        bounded_duration = max(0, int(duration_ms))
        key = self._ensure_unique_key(normalized_name)
        self._durations_ms[key] = bounded_duration

    def record_since_ms(self, name: str, started_ms: int) -> None:
        self.record_duration_ms(name, monotonic_ms() - int(started_ms))

    def record_elapsed_ms(self, name: str) -> None:
        self.record_duration_ms(name, monotonic_ms() - int(self.start_ms))

    def payload(self) -> dict[str, int]:
        return dict(self._durations_ms)

    def payload_json(self) -> str:
        payload = self.payload()
        return serialize_json_compact_stable(payload, ensure_ascii=False)

    def _ensure_unique_key(self, name: str) -> str:
        if name not in self._durations_ms:
            return name
        index = 2
        while True:
            candidate = f"{name}#{index}"
            if candidate not in self._durations_ms:
                return candidate
            index += 1
