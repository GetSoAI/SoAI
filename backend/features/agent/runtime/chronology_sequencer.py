"""SoAI - Agent event chronology sequencer service [backend/features/agent/runtime/chronology_sequencer.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from core.agent.protocols import AgentChronologySequencerProtocol
from core.conversations.protocols_database_agents import (
    DatabaseAgentEventSequencesProtocol,
)
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError, ValidationError
from core.types.json_value import coerce_json_dict
from core.users.user_id import require_strict_user_id
from core.validation.record_fields import require_int

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "AgentChronologySequencer",
    "AgentChronologySequencerDependencies",
)


@dataclass(frozen=True, slots=True)
class AgentChronologySequencerDependencies:
    database_agent_event_sequences: DatabaseAgentEventSequencesProtocol
    lease_size: int = 256
    max_states: int = 4096
    idle_ttl_seconds: float = 3600.0

    def __post_init__(self) -> None:
        require_dependencies(
            owner="AgentChronologySequencerDependencies",
            database_agent_event_sequences=self.database_agent_event_sequences,
            idle_ttl_seconds=self.idle_ttl_seconds,
            lease_size=self.lease_size,
            max_states=self.max_states,
        )
        if isinstance(self.lease_size, bool) or int(self.lease_size) < 1:
            raise ValidationError("Agent chronology lease_size must be a positive integer.")
        if isinstance(self.max_states, bool) or int(self.max_states) < 1:
            raise ValidationError("Agent chronology max_states must be a positive integer.")
        if isinstance(self.idle_ttl_seconds, bool) or float(self.idle_ttl_seconds) <= 0.0:
            raise ValidationError("Agent chronology idle_ttl_seconds must be a positive number.")


@dataclass(slots=True)
class _ChronologyLeaseState:
    lock: asyncio.Lock
    initialized: bool
    next_sequence: int
    lease_end_sequence: int
    last_issued: int
    last_touched_monotonic: float


def _normalize_key(*, conv_id: str, user_id: int) -> tuple[str, int]:
    normalized_conv_id = str(conv_id or "").strip()
    if not normalized_conv_id:
        raise ValidationError("conv_id must be a non-empty string.")
    normalized_user_id = require_strict_user_id(user_id)
    return (normalized_conv_id, normalized_user_id)


def _require_range_value(payload: JSONDict, *, field_name: str) -> int:
    return require_int(
        payload.get(field_name),
        label=field_name,
        build_error=StateError,
        minimum=0,
        invalid_message=f"Agent chronology allocator returned an invalid {field_name}.",
    )


class AgentChronologySequencer(AgentChronologySequencerProtocol):
    def __init__(self, deps: AgentChronologySequencerDependencies) -> None:
        self._database_agent_event_sequences = deps.database_agent_event_sequences
        self._lease_size = int(deps.lease_size)
        self._max_states = int(deps.max_states)
        self._idle_ttl_seconds = float(deps.idle_ttl_seconds)
        self._states: dict[tuple[str, int], _ChronologyLeaseState] = {}
        self._states_lock = asyncio.Lock()

    @override
    async def next_sequence(self, *, conv_id: str, user_id: int) -> int:
        key = _normalize_key(conv_id=conv_id, user_id=user_id)
        state = await self._get_or_create_state(key)
        async with state.lock:
            self._touch_state(state)
            await self._initialize_state_locked(key, state)
            await self._ensure_lease_locked(key, state)
            sequence = int(state.next_sequence)
            state.next_sequence = int(state.next_sequence) + 1
            if sequence > state.last_issued:
                state.last_issued = int(sequence)
            self._touch_state(state)
            return sequence

    @override
    def peek_last_issued(self, *, conv_id: str, user_id: int) -> int:
        key = _normalize_key(conv_id=conv_id, user_id=user_id)
        state = self._states.get(key)
        if state is None:
            return 0
        return int(state.last_issued)

    async def _get_or_create_state(self, key: tuple[str, int]) -> _ChronologyLeaseState:
        async with self._states_lock:
            self._prune_states_locked()
            existing_locked = self._states.get(key)
            if existing_locked is not None:
                self._touch_state(existing_locked)
                return existing_locked
            created = _ChronologyLeaseState(
                lock=asyncio.Lock(),
                initialized=False,
                next_sequence=1,
                lease_end_sequence=0,
                last_issued=0,
                last_touched_monotonic=time.monotonic(),
            )
            self._states[key] = created
            self._prune_states_locked(preserve_key=key)
            return created

    @staticmethod
    def _touch_state(state: _ChronologyLeaseState) -> None:
        state.last_touched_monotonic = time.monotonic()

    def _prune_states_locked(self, preserve_key: tuple[str, int] | None = None) -> None:
        now_monotonic = time.monotonic()
        expired_keys: list[tuple[str, int]] = []
        for state_key, state in self._states.items():
            if preserve_key is not None and state_key == preserve_key:
                continue
            if state.lock.locked():
                continue
            if (now_monotonic - state.last_touched_monotonic) > self._idle_ttl_seconds:
                expired_keys.append(state_key)
        for state_key in expired_keys:
            self._states.pop(state_key, None)
        excess_states = len(self._states) - self._max_states
        if excess_states <= 0:
            return
        least_recently_touched = sorted(
            [
                (state_key, state)
                for state_key, state in self._states.items()
                if (preserve_key is None or state_key != preserve_key) and not state.lock.locked()
            ],
            key=lambda item: item[1].last_touched_monotonic,
        )
        for state_key, _state in least_recently_touched:
            if len(self._states) <= self._max_states:
                break
            self._states.pop(state_key, None)

    async def _initialize_state_locked(
        self,
        key: tuple[str, int],
        state: _ChronologyLeaseState,
    ) -> None:
        if state.initialized:
            return
        conv_id, user_id = key
        current_sequence = await self._database_agent_event_sequences.get_current_sequence(
            conv_id=conv_id,
            user_id=user_id,
        )
        if isinstance(current_sequence, bool):
            raise StateError(
                "Agent chronology allocator returned an invalid current sequence value.",
            )
        normalized_current_sequence = int(current_sequence or 0)
        if normalized_current_sequence < 0:
            raise StateError(
                "Agent chronology allocator returned an invalid current sequence value.",
            )
        state.next_sequence = normalized_current_sequence + 1
        state.lease_end_sequence = normalized_current_sequence
        state.last_issued = normalized_current_sequence
        state.initialized = True

    async def _ensure_lease_locked(
        self,
        key: tuple[str, int],
        state: _ChronologyLeaseState,
    ) -> None:
        conv_id, user_id = key
        while state.next_sequence > state.lease_end_sequence:
            payload_raw = await self._database_agent_event_sequences.reserve_sequence_range(
                conv_id=conv_id,
                user_id=user_id,
                count=self._lease_size,
            )
            payload = coerce_json_dict(payload_raw)
            if payload is None:
                raise StateError("Agent chronology allocator returned an invalid payload.")
            start_sequence = _require_range_value(payload, field_name="start_sequence")
            end_sequence = _require_range_value(payload, field_name="end_sequence")
            if start_sequence <= 0 or end_sequence < start_sequence:
                raise StateError("Agent chronology allocator returned an invalid sequence range.")
            state.last_issued = max(state.last_issued, start_sequence - 1)
            state.next_sequence = max(state.next_sequence, start_sequence)
            state.lease_end_sequence = max(state.lease_end_sequence, end_sequence)
