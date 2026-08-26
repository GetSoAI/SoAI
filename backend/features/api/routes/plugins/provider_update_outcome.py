"""SoAI - Provider update transaction outcome projection [backend/features/api/routes/plugins/provider_update_outcome.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request
from starlette.responses import Response

from core.database.provider_mutation_requests import ProviderMutationOutcome
from core.models.external_provider_record import (
    ExternalProviderInternalRecord,
    ExternalProviderRecord,
)
from features.api.routes.plugins.provider_lifecycle_operations import (
    coerce_provider_record_or_server_error,
)
from features.api.runtime.errors import raise_conflict, raise_not_found

__all__ = ("resolve_provider_update_outcome",)


def resolve_provider_update_outcome(
    request: Request,
    response: Response,
    provider_id: str,
    canonical_plugin_name: str,
    outcome: ProviderMutationOutcome,
    provider: ExternalProviderInternalRecord | None,
) -> ExternalProviderRecord:
    if outcome.outcome == "stale_revision":
        raise_conflict(
            request,
            "Provider changed during the update. Refresh and retry.",
            error_type="stale_revision",
        )
    if outcome.outcome == "conflict":
        raise_conflict(
            request,
            "A provider with the requested URL or name already exists.",
            error_type="conflict",
        )
    if outcome.outcome == "not_found" or provider is None:
        raise_not_found(request, f"Provider with ID '{provider_id}' not found.")
    updated_record = coerce_provider_record_or_server_error(
        request,
        provider,
        label="Updated provider record",
    )
    if updated_record["plugin_name"] != canonical_plugin_name:
        raise_not_found(request, f"Provider with ID '{provider_id}' not found.")
    response.headers["ETag"] = f'"{updated_record["revision"]}"'
    return updated_record
