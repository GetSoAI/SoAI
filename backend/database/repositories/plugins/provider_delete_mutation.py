"""SoAI - Transactional provider deletion [backend/database/repositories/plugins/provider_delete_mutation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.database.provider_mutation_requests import (
    ProviderDeleteMutationRequest,
    ProviderMutationOutcome,
)
from core.errors.exceptions import StateError
from core.serialization.json import serialize_json_compact_stable_strict
from database.repositories.plugins.provider_mutation_outbox import (
    enqueue_provider_invalidations,
)
from database.repositories.plugins.provider_mutation_persistence import (
    admit_provider_revision_mutation,
    digest_provider_mutation_request,
    persist_provider_mutation_outcome,
)
from database.repositories.plugins.provider_mutation_validation import (
    require_expected_provider_revision,
)

__all__ = ("sync_delete_provider_v1",)

if TYPE_CHECKING:
    from typing import Literal

    ProviderDeleteOutcomeType = Literal["deleted", "not_found", "stale_revision"]


def sync_delete_provider_v1(
    connection: sqlite3.Connection,
    request: ProviderDeleteMutationRequest,
) -> ProviderMutationOutcome:
    expected_revision = require_expected_provider_revision(request.expected_revision)
    request_digest = digest_provider_mutation_request(serialize_json_compact_stable_strict({}))
    replay, current_revision = admit_provider_revision_mutation(
        connection,
        request,
        operation_type="delete",
        expected_revision=expected_revision,
        request_digest=request_digest,
    )
    if replay is not None:
        return replay
    result_outcome: ProviderDeleteOutcomeType
    result_revision: int | None
    if current_revision is None:
        result_outcome = "not_found"
        result_revision = None
    elif current_revision != expected_revision:
        result_outcome = "stale_revision"
        result_revision = current_revision
    else:
        connection.execute(
            "DELETE FROM models_catalog WHERE provider_id = ? AND plugin_name = ?",
            (request.provider_id, request.plugin_name),
        )
        deleted = connection.execute(
            "DELETE FROM models_external_providers WHERE id = ? AND plugin_name = ? AND revision = ?",
            (request.provider_id, request.plugin_name, expected_revision),
        ).rowcount
        if deleted != 1:
            raise StateError("Provider revision changed during the owning database transaction.")
        result_outcome = "deleted"
        result_revision = expected_revision
    outcome = persist_provider_mutation_outcome(
        connection,
        operation_id=request.operation_id,
        owner_id=request.owner_id,
        operation_type="delete",
        plugin_name=request.plugin_name,
        provider_id=request.provider_id,
        expected_revision=expected_revision,
        request_digest=request_digest,
        outcome=result_outcome,
        revision=result_revision,
        accepted_at_ms=request.accepted_at_ms,
    )
    if outcome.outcome == "deleted":
        enqueue_provider_invalidations(
            connection,
            request.operation_id,
            request.plugin_name,
            request.provider_id,
            "DELETED",
            expected_revision,
            request.accepted_at_ms,
        )
    return outcome
