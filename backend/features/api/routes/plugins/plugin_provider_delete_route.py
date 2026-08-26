"""SoAI - External provider delete endpoint [backend/features/api/routes/plugins/plugin_provider_delete_route.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from starlette.responses import Response

from core.database.provider_mutation_requests import ProviderDeleteMutationRequest
from core.errors.exceptions import ValidationError
from core.runtime.ownership import resolve_http_owner_id
from core.timing.epoch import epoch_ms
from features.api.routes.plugins.provider_lifecycle_operations import (
    ensure_external_provider_support,
)
from features.api.routes.plugins.provider_mutation_failure import (
    raise_provider_mutation_failure,
)
from features.api.routes.plugins.provider_mutation_headers import (
    require_provider_revision,
)
from features.api.runtime.audit import log_audit_event
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import (
    raise_conflict,
    raise_invalid_request,
    raise_not_found,
)
from features.api.runtime.idempotency import require_idempotency_key
from features.api.runtime.responses import create_no_content_response

__all__ = ("provider_delete_external",)

OPERATION = "api_plugin.provider_delete_external"


async def provider_delete_external(
    request: Request,
    plugin_name: str,
    provider_id: str,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    try:
        operation_id = require_idempotency_key(request)
        expected_revision = require_provider_revision(request)
    except ValidationError as exception:
        raise_invalid_request(request, exception.message)
    canonical_plugin_name, display_name = await ensure_external_provider_support(
        request,
        plugin_name,
        api_context.dependencies.plugin_manager,
    )
    log_audit_event(
        request,
        "DELETE_PROVIDER",
        provider_id,
        {"plugin": canonical_plugin_name, "display_name": display_name},
    )
    try:
        outcome = (
            await api_context.dependencies.model_provider_coordinator.provider_delete_external_v1(
                ProviderDeleteMutationRequest(
                    operation_id=operation_id,
                    owner_id=resolve_http_owner_id(request.state.context),
                    plugin_name=canonical_plugin_name,
                    provider_id=provider_id,
                    expected_revision=expected_revision,
                    accepted_at_ms=epoch_ms(),
                )
            )
        )
        if outcome.outcome == "stale_revision":
            raise_conflict(
                request,
                "Provider changed during deletion. Refresh and retry.",
                error_type="stale_revision",
            )
        if outcome.outcome == "not_found":
            raise_not_found(request, f"Provider with ID '{provider_id}' not found.")
        return create_no_content_response()
    except (ValidationError, ValueError, RuntimeError) as exception:
        raise_provider_mutation_failure(
            request,
            exception,
            operation=OPERATION,
            provider_id=provider_id,
            action="deleting",
        )
