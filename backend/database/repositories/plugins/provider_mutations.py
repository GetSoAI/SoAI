"""SoAI - Transactional provider mutations [backend/database/repositories/plugins/provider_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from cryptography.fernet import Fernet

from core.database.provider_mutation_requests import (
    ProviderCreateMutationRequest,
    ProviderMutationOutcome,
    ProviderUpdateMutationRequest,
)
from core.errors.exceptions import StateError, ValidationError
from core.models.external_provider_public_projection import sanitize_provider_audit
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_dict
from database.core.sqlite_values import SQLiteValue
from database.repositories.plugins.provider_mutation_conflicts import (
    read_provider_conflict_revision,
)
from database.repositories.plugins.provider_mutation_outbox import (
    enqueue_provider_invalidations,
)
from database.repositories.plugins.provider_mutation_persistence import (
    admit_provider_mutation,
    admit_provider_revision_mutation,
    digest_provider_mutation_request,
    persist_provider_mutation_outcome,
)
from database.repositories.plugins.provider_mutation_validation import (
    normalize_provider_updates,
    require_expected_provider_revision,
    require_provider_validation_state,
)
from database.repositories.plugins.provider_read_queries import sync_get_external_provider

__all__ = ("sync_create_provider_v1", "sync_update_provider_v1")


def _serialize_provider_projection(
    connection: sqlite3.Connection,
    fernet: tuple[Fernet, ...],
    provider_id: str,
) -> str:
    provider = sync_get_external_provider(connection, fernet, provider_id, decrypt_key=False)
    if provider is None:
        raise StateError("Committed provider projection is unavailable.")
    safe_provider = sanitize_provider_audit(provider)
    return serialize_json_compact_stable_strict(safe_provider)


def sync_create_provider_v1(
    connection: sqlite3.Connection,
    request: ProviderCreateMutationRequest,
    fernet: tuple[Fernet, ...],
) -> ProviderMutationOutcome:
    provider_fields = parse_json_dict(request.provider_json, field="provider_json")
    normalized_fields = normalize_provider_updates(provider_fields, fernet)
    if "api_url" not in normalized_fields:
        raise ValidationError("Provider creation requires api_url.")
    validation_status, validation_error, validated_at_ms = require_provider_validation_state(
        request.validation_status,
        request.validation_error,
        request.validated_at_ms,
    )
    request_json = serialize_json_compact_stable_strict(provider_fields)
    request_digest = digest_provider_mutation_request(request_json)
    replay = admit_provider_mutation(
        connection,
        request.operation_id,
        request.owner_id,
        "create",
        request.plugin_name,
        request.provider_id,
        0,
        request_digest,
        request.accepted_at_ms,
    )
    if replay is not None:
        return replay
    conflict_revision = read_provider_conflict_revision(
        connection,
        plugin_name=request.plugin_name,
        provider_id=request.provider_id,
        normalized_fields=normalized_fields,
        include_same_id=True,
    )
    if conflict_revision is not None:
        return persist_provider_mutation_outcome(
            connection,
            operation_id=request.operation_id,
            owner_id=request.owner_id,
            operation_type="create",
            plugin_name=request.plugin_name,
            provider_id=request.provider_id,
            expected_revision=0,
            request_digest=request_digest,
            outcome="conflict",
            revision=conflict_revision,
            accepted_at_ms=request.accepted_at_ms,
        )
    columns = tuple(normalized_fields)
    assignments = ", ".join(columns)
    placeholders = ", ".join("?" for _ in columns)
    connection.execute(
        f"INSERT INTO models_external_providers (id, plugin_name, {assignments}, created_at_ms, last_status, last_error, last_checked_at_ms) VALUES (?, ?, {placeholders}, ?, ?, ?, ?)",
        (
            request.provider_id,
            request.plugin_name,
            *normalized_fields.values(),
            request.accepted_at_ms,
            validation_status,
            validation_error,
            validated_at_ms,
        ),
    )
    outcome = persist_provider_mutation_outcome(
        connection,
        operation_id=request.operation_id,
        owner_id=request.owner_id,
        operation_type="create",
        plugin_name=request.plugin_name,
        provider_id=request.provider_id,
        expected_revision=0,
        request_digest=request_digest,
        outcome="created",
        revision=0,
        accepted_at_ms=request.accepted_at_ms,
        provider_json=_serialize_provider_projection(
            connection,
            fernet,
            request.provider_id,
        ),
    )
    enqueue_provider_invalidations(
        connection,
        request.operation_id,
        request.plugin_name,
        request.provider_id,
        validation_status,
        0,
        request.accepted_at_ms,
    )
    return outcome


def sync_update_provider_v1(
    connection: sqlite3.Connection,
    request: ProviderUpdateMutationRequest,
    fernet: tuple[Fernet, ...] | None = None,
) -> ProviderMutationOutcome:
    expected_revision = require_expected_provider_revision(request.expected_revision)
    updates = parse_json_dict(request.updates_json, field="updates_json")
    normalized_updates = normalize_provider_updates(updates, fernet)
    validation_status, validation_error, validated_at_ms = require_provider_validation_state(
        request.validation_status,
        request.validation_error,
        request.validated_at_ms,
    )
    normalized_updates["last_status"] = validation_status
    normalized_updates["last_error"] = validation_error
    normalized_updates["last_checked_at_ms"] = validated_at_ms
    request_json = serialize_json_compact_stable_strict(updates)
    request_digest = digest_provider_mutation_request(request_json)
    replay, current_revision = admit_provider_revision_mutation(
        connection,
        request,
        operation_type="update",
        expected_revision=expected_revision,
        request_digest=request_digest,
    )
    if replay is not None:
        return replay
    if current_revision is None:
        return persist_provider_mutation_outcome(
            connection,
            operation_id=request.operation_id,
            owner_id=request.owner_id,
            operation_type="update",
            plugin_name=request.plugin_name,
            provider_id=request.provider_id,
            expected_revision=expected_revision,
            request_digest=request_digest,
            outcome="not_found",
            revision=None,
            accepted_at_ms=request.accepted_at_ms,
        )
    if current_revision != expected_revision:
        return persist_provider_mutation_outcome(
            connection,
            operation_id=request.operation_id,
            owner_id=request.owner_id,
            operation_type="update",
            plugin_name=request.plugin_name,
            provider_id=request.provider_id,
            expected_revision=expected_revision,
            request_digest=request_digest,
            outcome="stale_revision",
            revision=current_revision,
            accepted_at_ms=request.accepted_at_ms,
        )
    uniqueness_fields: dict[str, SQLiteValue] = {}
    if "api_url" in normalized_updates:
        uniqueness_fields["api_url"] = normalized_updates["api_url"]
    else:
        current_url = connection.execute(
            "SELECT api_url FROM models_external_providers WHERE id = ?",
            (request.provider_id,),
        ).fetchone()
        if current_url is None:
            raise StateError("Provider disappeared during the owning database transaction.")
        uniqueness_fields["api_url"] = current_url["api_url"]
    if "canonical_name" in normalized_updates:
        uniqueness_fields["canonical_name"] = normalized_updates["canonical_name"]
    conflict_revision = read_provider_conflict_revision(
        connection,
        plugin_name=request.plugin_name,
        provider_id=request.provider_id,
        normalized_fields=uniqueness_fields,
        include_same_id=False,
    )
    if conflict_revision is not None:
        return persist_provider_mutation_outcome(
            connection,
            operation_id=request.operation_id,
            owner_id=request.owner_id,
            operation_type="update",
            plugin_name=request.plugin_name,
            provider_id=request.provider_id,
            expected_revision=expected_revision,
            request_digest=request_digest,
            outcome="conflict",
            revision=conflict_revision,
            accepted_at_ms=request.accepted_at_ms,
        )
    assignments = ", ".join(f"{field_name} = ?" for field_name in normalized_updates)
    new_revision = expected_revision + 1
    values = tuple(normalized_updates.values())
    updated = connection.execute(
        f"UPDATE models_external_providers SET {assignments}, revision = ? WHERE id = ? AND plugin_name = ? AND revision = ?",
        values + (new_revision, request.provider_id, request.plugin_name, expected_revision),
    ).rowcount
    if updated != 1:
        raise StateError("Provider revision changed during the owning database transaction.")
    outcome = persist_provider_mutation_outcome(
        connection,
        operation_id=request.operation_id,
        owner_id=request.owner_id,
        operation_type="update",
        plugin_name=request.plugin_name,
        provider_id=request.provider_id,
        expected_revision=expected_revision,
        request_digest=request_digest,
        outcome="updated",
        revision=new_revision,
        accepted_at_ms=request.accepted_at_ms,
        provider_json=_serialize_provider_projection(
            connection,
            fernet or (),
            request.provider_id,
        ),
    )
    enqueue_provider_invalidations(
        connection,
        request.operation_id,
        request.plugin_name,
        request.provider_id,
        validation_status,
        new_revision,
        request.accepted_at_ms,
    )
    return outcome
