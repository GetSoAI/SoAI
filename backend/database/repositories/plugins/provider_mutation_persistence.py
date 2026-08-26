"""SoAI - Provider mutation validation and persistence [backend/database/repositories/plugins/provider_mutation_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.database.provider_mutation_requests import (
    ProviderDeleteMutationRequest,
    ProviderMutationOutcome,
    ProviderMutationReplayRequest,
    ProviderUpdateMutationRequest,
)
from core.errors.exceptions import StateError
from core.mutations.identifiers import (
    extract_mutation_request_timestamp_ms,
    require_mutation_request_id,
)
from core.mutations.identity_window import (
    IDENTITY_RETENTION_MS,
    validate_mutation_identity_window,
)
from database.repositories.plugins.provider_mutation_conflicts import read_provider_revision
from database.repositories.plugins.provider_mutation_validation import (
    require_provider_mutation_metadata,
)

if TYPE_CHECKING:
    from typing import Literal

    ProviderMutationOutcomeType = Literal[
        "created",
        "updated",
        "deleted",
        "conflict",
        "stale_revision",
        "not_found",
    ]

__all__ = (
    "digest_provider_mutation_request",
    "persist_provider_mutation_outcome",
    "read_provider_mutation_outcome",
    "admit_provider_mutation",
    "admit_provider_revision_mutation",
)


def _require_provider_mutation_outcome(value: str) -> ProviderMutationOutcomeType:
    if value == "created":
        return "created"
    if value == "updated":
        return "updated"
    if value == "deleted":
        return "deleted"
    if value == "conflict":
        return "conflict"
    if value == "stale_revision":
        return "stale_revision"
    if value == "not_found":
        return "not_found"
    raise StateError("Persisted provider mutation outcome is invalid.")


def _provider_mutation_outcome_from_row(
    row: sqlite3.Row | None,
    owner_id: str,
    operation_type: str,
    plugin_name: str,
    provider_id: str,
    expected_revision: int,
    request_digest: str,
) -> ProviderMutationOutcome | None:
    if row is None:
        return None
    if row["owner_id"] != owner_id:
        raise PermissionError("Provider mutation identity belongs to another owner.")
    expected = (operation_type, plugin_name, provider_id, expected_revision, request_digest)
    persisted = tuple(
        row[field_name]
        for field_name in (
            "operation_type",
            "plugin_name",
            "provider_id",
            "expected_revision",
            "request_digest",
        )
    )
    if persisted != expected:
        raise StateError("Provider mutation identity was reused with different input.")
    return ProviderMutationOutcome(
        outcome=_require_provider_mutation_outcome(row["outcome"]),
        provider_id=row["provider_id"],
        revision=row["provider_revision"],
        provider_json=row["provider_json"],
    )


def _read_provider_mutation_outcome(
    connection: sqlite3.Connection,
    operation_id: str,
    owner_id: str,
    operation_type: str,
    plugin_name: str,
    provider_id: str,
    expected_revision: int,
    request_digest: str,
) -> ProviderMutationOutcome | None:
    row = connection.execute(
        "SELECT * FROM provider_mutation_outcomes WHERE operation_id = ?",
        (operation_id,),
    ).fetchone()
    return _provider_mutation_outcome_from_row(
        row,
        owner_id,
        operation_type,
        plugin_name,
        provider_id,
        expected_revision,
        request_digest,
    )


async def read_provider_mutation_outcome(
    connection: aiosqlite.Connection,
    request: ProviderMutationReplayRequest,
) -> ProviderMutationOutcome | None:
    require_mutation_request_id(request.operation_id)
    async with connection.execute(
        "SELECT * FROM provider_mutation_outcomes WHERE operation_id = ?",
        (request.operation_id,),
    ) as cursor:
        row = await cursor.fetchone()
    return _provider_mutation_outcome_from_row(
        row,
        request.owner_id,
        request.operation_type,
        request.plugin_name,
        request.provider_id,
        request.expected_revision,
        digest_provider_mutation_request(request.request_json),
    )


def admit_provider_mutation(
    connection: sqlite3.Connection,
    operation_id: str,
    owner_id: str,
    operation_type: str,
    plugin_name: str,
    provider_id: str,
    expected_revision: int,
    request_digest: str,
    accepted_at_ms: int,
) -> ProviderMutationOutcome | None:
    require_provider_mutation_metadata(
        owner_id,
        plugin_name,
        provider_id,
        accepted_at_ms,
    )
    require_mutation_request_id(operation_id)
    connection.execute(
        """INSERT INTO provider_mutation_clock (singleton_id, server_time_watermark_ms)
        VALUES (1, ?)
        ON CONFLICT(singleton_id) DO UPDATE SET server_time_watermark_ms =
            max(server_time_watermark_ms, excluded.server_time_watermark_ms)""",
        (accepted_at_ms,),
    )
    watermark_ms = connection.execute(
        "SELECT server_time_watermark_ms FROM provider_mutation_clock WHERE singleton_id = 1"
    ).fetchone()[0]
    connection.execute(
        "DELETE FROM provider_mutation_outcomes WHERE expires_at_ms < ?",
        (watermark_ms,),
    )
    replay = _read_provider_mutation_outcome(
        connection,
        operation_id,
        owner_id,
        operation_type,
        plugin_name,
        provider_id,
        expected_revision,
        request_digest,
    )
    if replay is None:
        validate_mutation_identity_window(operation_id, watermark_ms)
    return replay


def admit_provider_revision_mutation(
    connection: sqlite3.Connection,
    request: ProviderDeleteMutationRequest | ProviderUpdateMutationRequest,
    *,
    operation_type: str,
    expected_revision: int,
    request_digest: str,
) -> tuple[ProviderMutationOutcome | None, int | None]:
    replay = admit_provider_mutation(
        connection,
        request.operation_id,
        request.owner_id,
        operation_type,
        request.plugin_name,
        request.provider_id,
        expected_revision,
        request_digest,
        request.accepted_at_ms,
    )
    if replay is not None:
        return (replay, None)
    return (
        None,
        read_provider_revision(
            connection,
            plugin_name=request.plugin_name,
            provider_id=request.provider_id,
        ),
    )


def persist_provider_mutation_outcome(
    connection: sqlite3.Connection,
    *,
    operation_id: str,
    owner_id: str,
    operation_type: str,
    plugin_name: str,
    provider_id: str,
    expected_revision: int,
    request_digest: str,
    outcome: str,
    revision: int | None,
    accepted_at_ms: int,
    provider_json: str | None = None,
) -> ProviderMutationOutcome:
    connection.execute(
        """INSERT INTO provider_mutation_outcomes (
            operation_id, owner_id, operation_type, plugin_name, provider_id,
            expected_revision, request_digest, outcome, provider_revision, provider_json,
            accepted_at_ms, expires_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            operation_id,
            owner_id,
            operation_type,
            plugin_name,
            provider_id,
            expected_revision,
            request_digest,
            outcome,
            revision,
            provider_json,
            accepted_at_ms,
            extract_mutation_request_timestamp_ms(operation_id) + IDENTITY_RETENTION_MS,
        ),
    )
    return ProviderMutationOutcome(
        outcome=_require_provider_mutation_outcome(outcome),
        provider_id=provider_id,
        revision=revision,
        provider_json=provider_json,
    )


def digest_provider_mutation_request(request_json: str) -> str:
    return hashlib.sha256(request_json.encode("utf-8")).hexdigest()
