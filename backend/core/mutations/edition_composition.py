"""SoAI - Durable mutation edition composition contract [backend/core/mutations/edition_composition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from core.events.types_base import ReplyableCommand
from core.mutations.protocols import MutationClaimProtocol, MutationDecoderProtocol
from core.mutations.storage_composition import MutationStorageComposition

__all__ = ("DurableMutationComposition",)


@dataclass(frozen=True, slots=True)
class DurableMutationComposition:
    operation_matches: Callable[[str], bool] | None
    decode_command: MutationDecoderProtocol | None
    claim_expired: MutationClaimProtocol | None
    command_is_recovery: Callable[[ReplyableCommand, int], bool] | None
    command_requested_recovery: Callable[[ReplyableCommand], bool] | None
    storage: MutationStorageComposition
