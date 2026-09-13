"""SoAI - Plugin guardian flapping detection helper [backend/plugins/guardian_flapping.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections import deque
from collections.abc import Collection

__all__ = (
    "FLAPPING_HISTORY_CAPACITY",
    "collect_recent_state_transitions",
    "is_flapping",
    "record_state_transition",
)

FLAPPING_HISTORY_CAPACITY = 129


def collect_recent_state_transitions(
    history: deque[tuple[str, float]],
    *,
    now_monotonic: float,
    window_seconds: float,
) -> tuple[str, ...]:
    if window_seconds <= 0:
        return ()
    cutoff = now_monotonic - window_seconds
    recent_states: list[str] = []
    for state, observed_at in history:
        if observed_at < cutoff or observed_at > now_monotonic:
            continue
        if recent_states and recent_states[-1] == state:
            continue
        recent_states.append(state)
    return tuple(recent_states)


def record_state_transition(
    history: deque[tuple[str, float]],
    state: str,
    *,
    observed_at: float,
) -> None:
    observations = sorted((*history, (state, observed_at)), key=lambda entry: entry[1])
    ordered_history: deque[tuple[str, float]] = deque(maxlen=history.maxlen)
    for observed_state, timestamp in observations:
        if ordered_history and ordered_history[-1][0] == observed_state:
            ordered_history[-1] = (observed_state, timestamp)
        else:
            ordered_history.append((observed_state, timestamp))
    history.clear()
    history.extend(ordered_history)


def is_flapping(
    history: deque[tuple[str, float]],
    failure_states: Collection[str],
    *,
    now_monotonic: float,
    window_seconds: float,
    min_transitions: int,
) -> bool:
    if min_transitions < 3 or window_seconds <= 0:
        return False
    recent_states = collect_recent_state_transitions(
        history,
        now_monotonic=now_monotonic,
        window_seconds=window_seconds,
    )
    if len(recent_states) - 1 < min_transitions:
        return False
    failure_observations = sum(state in failure_states for state in recent_states)
    return len(set(recent_states)) >= 2 and 2 <= failure_observations < len(recent_states)
