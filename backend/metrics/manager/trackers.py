"""SoAI - Metrics rate trackers [backend/metrics/manager/trackers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock

from core.openai.token_rate_calculation import calculate_smoothed_token_rate

__all__ = ("TokenRateTracker",)

TOKEN_RATE_SHORT_WINDOW_MS = 5_000
TOKEN_RATE_LONG_WINDOW_MS = 30_000


@dataclass(slots=True)
class TokenStreamState:
    plugin: str
    last_token_at_ms: int | None
    effective_rate: float


class TokenRateTracker:
    def __init__(self) -> None:
        self.lock = Lock()
        self.plugin_token_events: dict[str, deque[tuple[int, int]]] = defaultdict(deque)
        self.total_token_events: deque[tuple[int, int]] = deque()
        self.active_streams: dict[str, TokenStreamState] = {}

    def _prune_expired_events(self, now_ms: int) -> None:
        cutoff_ms = now_ms - TOKEN_RATE_LONG_WINDOW_MS
        expired_plugins: list[str] = []
        for plugin, events in self.plugin_token_events.items():
            while events and events[0][0] < cutoff_ms:
                events.popleft()
            if not events:
                expired_plugins.append(plugin)
        for plugin in expired_plugins:
            self.plugin_token_events.pop(plugin, None)
        while self.total_token_events and self.total_token_events[0][0] < cutoff_ms:
            self.total_token_events.popleft()

    def begin_stream(self, stream_id: str, plugin: str, observed_at_ms: int) -> None:
        normalized_stream_id = stream_id.strip()
        normalized_plugin = plugin.strip()
        if not normalized_stream_id or not normalized_plugin or observed_at_ms < 0:
            return
        with self.lock:
            self._prune_expired_events(observed_at_ms)
            self.active_streams[normalized_stream_id] = TokenStreamState(
                plugin=normalized_plugin,
                last_token_at_ms=None,
                effective_rate=0.0,
            )

    def record_stream_delta(
        self,
        stream_id: str,
        plugin: str,
        token_delta: int,
        observed_at_ms: int,
    ) -> None:
        normalized_stream_id = stream_id.strip()
        normalized_plugin = plugin.strip()
        if (
            not normalized_stream_id
            or not normalized_plugin
            or token_delta < 0
            or observed_at_ms < 0
        ):
            return
        with self.lock:
            self._prune_expired_events(observed_at_ms)
            state = self.active_streams.get(normalized_stream_id)
            if state is None or state.plugin != normalized_plugin:
                state = TokenStreamState(
                    plugin=normalized_plugin,
                    last_token_at_ms=None,
                    effective_rate=0.0,
                )
                self.active_streams[normalized_stream_id] = state
            if token_delta <= 0:
                return
            previous_token_at_ms = state.last_token_at_ms
            if previous_token_at_ms is not None and observed_at_ms < previous_token_at_ms:
                return
            self.plugin_token_events[normalized_plugin].append(
                (observed_at_ms, token_delta),
            )
            self.total_token_events.append((observed_at_ms, token_delta))
            state.last_token_at_ms = observed_at_ms
            if previous_token_at_ms is None or observed_at_ms <= previous_token_at_ms:
                return
            state.effective_rate = calculate_smoothed_token_rate(
                previous_rate=state.effective_rate,
                token_delta=token_delta,
                elapsed_ms=observed_at_ms - previous_token_at_ms,
            )

    def record_completion_tokens(
        self,
        plugin: str,
        tokens: int,
        observed_at_ms: int,
    ) -> None:
        normalized_plugin = plugin.strip()
        if not normalized_plugin or tokens <= 0 or observed_at_ms < 0:
            return
        with self.lock:
            self._prune_expired_events(observed_at_ms)
            self.plugin_token_events[normalized_plugin].append((observed_at_ms, tokens))
            self.total_token_events.append((observed_at_ms, tokens))

    def finish_stream(self, stream_id: str, observed_at_ms: int) -> None:
        normalized_stream_id = stream_id.strip()
        if not normalized_stream_id or observed_at_ms < 0:
            return
        with self.lock:
            self._prune_expired_events(observed_at_ms)
            self.active_streams.pop(normalized_stream_id, None)

    def _calculate_window_rate(
        self,
        events: deque[tuple[int, int]],
        *,
        now_ms: int,
        window_ms: int,
    ) -> float:
        cutoff_ms = now_ms - window_ms
        tokens = sum(count for observed_at_ms, count in events if observed_at_ms >= cutoff_ms)
        return float(tokens) * 1000.0 / float(window_ms)

    def _build_rate_payload(
        self,
        events: deque[tuple[int, int]],
        *,
        effective_rate: float,
        active_streams: int,
        now_ms: int,
    ) -> dict[str, float | int]:
        return {
            "effective_rate": round(effective_rate, 2),
            "delivered_rate_5s": round(
                self._calculate_window_rate(
                    events,
                    now_ms=now_ms,
                    window_ms=TOKEN_RATE_SHORT_WINDOW_MS,
                ),
                2,
            ),
            "delivered_rate_30s": round(
                self._calculate_window_rate(
                    events,
                    now_ms=now_ms,
                    window_ms=TOKEN_RATE_LONG_WINDOW_MS,
                ),
                2,
            ),
            "active_streams": active_streams,
        }

    def get_rates(
        self,
        now_ms: int,
    ) -> dict[str, dict[str, float | int] | dict[str, dict[str, float | int]]]:
        with self.lock:
            self._prune_expired_events(now_ms)
            plugin_effective_rates: dict[str, float] = defaultdict(float)
            plugin_active_streams: dict[str, int] = defaultdict(int)
            total_effective_rate = 0.0
            for state in self.active_streams.values():
                plugin_effective_rates[state.plugin] += state.effective_rate
                plugin_active_streams[state.plugin] += 1
                total_effective_rate += state.effective_rate
            plugin_names = (
                set(self.plugin_token_events)
                | set(plugin_effective_rates)
                | set(plugin_active_streams)
            )
            plugins = {
                plugin: self._build_rate_payload(
                    self.plugin_token_events.get(plugin, deque()),
                    effective_rate=plugin_effective_rates.get(plugin, 0.0),
                    active_streams=plugin_active_streams.get(plugin, 0),
                    now_ms=now_ms,
                )
                for plugin in plugin_names
            }
            total = self._build_rate_payload(
                self.total_token_events,
                effective_rate=total_effective_rate,
                active_streams=len(self.active_streams),
                now_ms=now_ms,
            )
            return {"total": total, "plugins": plugins}

    def reset(self) -> None:
        with self.lock:
            self.plugin_token_events.clear()
            self.total_token_events.clear()
            self.active_streams.clear()
