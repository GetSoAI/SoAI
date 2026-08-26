"""SoAI - Durable mutation subsystem recovery signals [backend/app/background/mutation_recovery_signals.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.events.types_base import ReplyableCommand
from core.mutations.edition_composition import DurableMutationComposition

__all__ = (
    "mutation_command_is_storage_recovery",
    "mutation_command_requested_recovery",
)


def mutation_command_is_storage_recovery(
    command: ReplyableCommand,
    attempt_count: int,
    durable_mutations: DurableMutationComposition,
) -> bool:
    predicate = durable_mutations.command_is_recovery
    return predicate is not None and predicate(command, attempt_count)


def mutation_command_requested_recovery(
    command: ReplyableCommand,
    durable_mutations: DurableMutationComposition,
) -> bool:
    predicate = durable_mutations.command_requested_recovery
    return predicate is not None and predicate(command)
