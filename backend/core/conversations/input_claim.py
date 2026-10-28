"""SoAI - Immutable conversation input execution claim identity [backend/core/conversations/input_claim.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exceptions import StateError
from core.validation.integers import is_strict_int

__all__ = ("ConversationInputClaim",)


@dataclass(frozen=True, slots=True)
class ConversationInputClaim:
    input_id: str
    generation: int
    owner: str
    server_boot_id: str

    def __post_init__(self) -> None:
        if not is_strict_int(self.generation) or self.generation < 1:
            raise StateError("Conversation input claim generation is unavailable.")
        if any(
            not value or value != value.strip()
            for value in (self.input_id, self.owner, self.server_boot_id)
        ):
            raise StateError("Conversation input claim identity is unavailable.")

    @classmethod
    def from_fields(
        cls,
        input_id: str | None,
        generation: int | None,
        owner: str | None,
        server_boot_id: str | None,
    ) -> ConversationInputClaim:
        if input_id is None or generation is None or owner is None or server_boot_id is None:
            raise StateError("Conversation input execution claim is unavailable.")
        return cls(input_id, generation, owner, server_boot_id)
