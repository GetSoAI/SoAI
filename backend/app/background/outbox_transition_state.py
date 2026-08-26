"""SoAI - Shared outbox terminal transition state and retry backoff [backend/app/background/outbox_transition_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.timing.retry_backoff import compute_exponential_backoff_milliseconds

__all__ = (
    "OutboxTransitionState",
    "PendingOutboxTerminalTransition",
    "compute_next_attempt_at_ms",
)


def compute_next_attempt_at_ms(attempts: int, *, now_ms: int) -> int:
    bounded_attempts = max(int(attempts) or 0, 0)
    delay_ms = compute_exponential_backoff_milliseconds(
        min(bounded_attempts, 8),
        base_milliseconds=250,
        maximum_milliseconds=30_000,
    )
    return int(now_ms) + int(min(delay_ms, 30_000))


@dataclass(frozen=True, slots=True)
class PendingOutboxTerminalTransition:
    transition_type: str
    attempts: int
    next_attempt_at_ms: int
    error_message: str
    published_at_ms: int | None = None
    event_id: str | None = None


class OutboxTransitionState:
    def __init__(self) -> None:
        self._quarantined_until_ms_by_outbox_id: dict[int, int] = {}
        self._pending_terminal_transitions: dict[int, PendingOutboxTerminalTransition] = {}

    def reset(self) -> None:
        self._quarantined_until_ms_by_outbox_id.clear()
        self._pending_terminal_transitions.clear()

    def quarantine(self, outbox_id: int, *, now_ms: int, delay_ms: int) -> None:
        until = int(now_ms) + max(0, int(delay_ms))
        existing = self._quarantined_until_ms_by_outbox_id.get(int(outbox_id))
        if existing is None or int(existing) < until:
            self._quarantined_until_ms_by_outbox_id[int(outbox_id)] = until

    def _is_quarantined(self, outbox_id: int, *, now_ms: int) -> bool:
        until = self._quarantined_until_ms_by_outbox_id.get(int(outbox_id))
        if until is None:
            return False
        if int(now_ms) >= int(until):
            self._quarantined_until_ms_by_outbox_id.pop(int(outbox_id), None)
            return False
        return True

    def should_skip_processing(self, outbox_id: int, *, now_ms: int | None = None) -> bool:
        normalized_outbox_id = int(outbox_id)
        if normalized_outbox_id in self._pending_terminal_transitions:
            return True
        if now_ms is None:
            return False
        return self._is_quarantined(normalized_outbox_id, now_ms=now_ms)

    def set_pending_transition(
        self,
        outbox_id: int,
        pending: PendingOutboxTerminalTransition,
    ) -> None:
        self._pending_terminal_transitions[int(outbox_id)] = pending

    def pending_items(self) -> tuple[tuple[int, PendingOutboxTerminalTransition], ...]:
        return tuple(self._pending_terminal_transitions.items())

    def clear_processing_delays(self, outbox_id: int) -> None:
        normalized_outbox_id = int(outbox_id)
        self._pending_terminal_transitions.pop(normalized_outbox_id, None)
        self._quarantined_until_ms_by_outbox_id.pop(normalized_outbox_id, None)
