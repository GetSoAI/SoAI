"""SoAI - Expired durable mutation claim recovery [backend/app/background/mutation_claim_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from filelock import Timeout

from core.concurrency.cancellation_cleanup import uncancel_and_wait
from core.database.mutation_requests import MutationClaim, MutationRecoveryCandidate
from core.database.protocols_tasks import DatabaseTasksProtocol
from core.errors.exceptions import StateError, ValidationError
from core.files.locking import async_guarded_file_lock
from core.mutations.edition_composition import DurableMutationComposition
from core.plugins.mutation_conflicts import extract_plugin_lifecycle_conflict_target
from core.plugins.portable_identifiers import require_portable_plugin_identifier
from plugins.lifecycle_advisory_lock import resolve_plugin_lifecycle_lock_path

__all__ = ("claim_expired_mutation_candidate",)


async def claim_expired_mutation_candidate(
    database_tasks: DatabaseTasksProtocol,
    candidate: MutationRecoveryCandidate,
    *,
    plugin_directory: str,
    worker_id: str,
    now_ms: int,
    lease_duration_ms: int,
    durable_mutations: DurableMutationComposition,
) -> MutationClaim | None:
    if candidate.conflict_keys != tuple(sorted(set(candidate.conflict_keys))):
        raise ValidationError("Mutation recovery requires canonical conflict identities.")
    plugin_names = tuple(
        require_portable_plugin_identifier(plugin_name, field_name="plugin_name")
        for conflict_key in candidate.conflict_keys
        if (plugin_name := extract_plugin_lifecycle_conflict_target(conflict_key)) is not None
    )
    operation_matches = durable_mutations.operation_matches
    if operation_matches is not None and operation_matches(candidate.operation_type):
        claim_extension = durable_mutations.claim_expired
        if claim_extension is None:
            raise StateError("Edition mutation recovery is unavailable.")
        return await claim_extension(
            database_tasks,
            candidate,
            plugin_directory=plugin_directory,
            worker_id=worker_id,
            now_ms=now_ms,
            lease_duration_ms=lease_duration_ms,
        )
    if (
        plugin_names != tuple(sorted(set(plugin_names)))
        or len(plugin_names)
        not in (
            1,
            2,
        )
        or len(plugin_names) != len(candidate.conflict_keys)
    ):
        raise ValidationError("Plugin mutation recovery requires canonical lock identities.")
    await uncancel_and_wait(
        asyncio.to_thread(
            os.makedirs,
            os.path.join(plugin_directory, ".locks"),
            mode=0o700,
            exist_ok=True,
        )
    )
    try:
        first_lock_path = resolve_plugin_lifecycle_lock_path(
            plugin_directory,
            plugin_names[0],
        )
        if len(plugin_names) == 1:
            async with async_guarded_file_lock(first_lock_path, timeout=0.0):
                return await database_tasks.claim_mutation(
                    candidate.request_id,
                    worker_id,
                    now_ms=now_ms,
                    lease_duration_ms=lease_duration_ms,
                )
        second_lock_path = resolve_plugin_lifecycle_lock_path(
            plugin_directory,
            plugin_names[1],
        )
        async with async_guarded_file_lock(first_lock_path, timeout=0.0):
            async with async_guarded_file_lock(second_lock_path, timeout=0.0):
                return await database_tasks.claim_mutation(
                    candidate.request_id,
                    worker_id,
                    now_ms=now_ms,
                    lease_duration_ms=lease_duration_ms,
                )
    except Timeout:
        return None
