"""SoAI - Authoritative OpenAI protection state transitions [backend/database/repositories/users/api_keys/protection_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.auth.openai_protection import OpenAIProtectionState
from core.validation.requirements import require_non_negative_exact_int

__all__ = ("OpenAIProtectionStateTracker",)


class OpenAIProtectionStateTracker:
    def __init__(self, configured_key_count: int) -> None:
        self._configured_key_count: int | None = self._validate_count(
            configured_key_count,
            label="Configured",
        )
        self._protection_state = self._state_for_count(configured_key_count)

    @property
    def protection_state(self) -> OpenAIProtectionState:
        return self._protection_state

    def enter_insert_submission(self) -> tuple[OpenAIProtectionState, int | None]:
        snapshot = self._snapshot()
        if self._protection_state is OpenAIProtectionState.OPEN:
            self._protection_state = OpenAIProtectionState.INDETERMINATE
        return snapshot

    def retain_uncertain_insert(
        self,
        snapshot: tuple[OpenAIProtectionState, int | None],
        *,
        committed: bool | None,
    ) -> None:
        previous_state, _previous_count = snapshot
        self._configured_key_count = None
        if previous_state is OpenAIProtectionState.REQUIRED or committed is True:
            self._protection_state = OpenAIProtectionState.REQUIRED
        else:
            self._protection_state = OpenAIProtectionState.INDETERMINATE

    def enter_deletion_submission(
        self,
        *,
        maximum_deleted_records: int | None,
    ) -> tuple[OpenAIProtectionState, int | None]:
        snapshot = self._snapshot()
        if self._protection_state is OpenAIProtectionState.OPEN:
            return snapshot
        configured_key_count = self._configured_key_count
        self._configured_key_count = None
        if (
            configured_key_count is not None
            and maximum_deleted_records is not None
            and configured_key_count > maximum_deleted_records
        ):
            self._protection_state = OpenAIProtectionState.REQUIRED
        else:
            self._protection_state = OpenAIProtectionState.INDETERMINATE
        return snapshot

    def restore(self, snapshot: tuple[OpenAIProtectionState, int | None]) -> None:
        self._protection_state, self._configured_key_count = snapshot

    def apply_committed_count(self, configured_key_count: int) -> None:
        validated_count = self._validate_count(configured_key_count, label="Remaining")
        self._configured_key_count = validated_count
        self._protection_state = self._state_for_count(validated_count)

    def _snapshot(self) -> tuple[OpenAIProtectionState, int | None]:
        return (self._protection_state, self._configured_key_count)

    @staticmethod
    def _state_for_count(configured_key_count: int) -> OpenAIProtectionState:
        if configured_key_count > 0:
            return OpenAIProtectionState.REQUIRED
        return OpenAIProtectionState.OPEN

    @staticmethod
    def _validate_count(configured_key_count: int, *, label: str) -> int:
        return require_non_negative_exact_int(
            configured_key_count,
            type_message=f"{label} OpenAI API key count must be an integer.",
            range_message=f"{label} OpenAI API key count must be non-negative.",
        )
