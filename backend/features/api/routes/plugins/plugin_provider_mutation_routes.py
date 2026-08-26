"""SoAI - External provider update/delete endpoints [backend/features/api/routes/plugins/plugin_provider_mutation_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request
from starlette.responses import Response

from core.database.provider_mutation_requests import (
    ProviderMutationReplayRequest,
    ProviderUpdateMutationRequest,
)
from core.errors.exceptions import ValidationError
from core.models.external_provider_public_projection import sanitize_provider_audit
from core.models.external_provider_record import ExternalProviderRecord
from core.runtime.ownership import resolve_http_owner_id
from core.serialization.json import serialize_json_compact_stable_strict
from core.state.access import AccessAction
from core.timing.epoch import epoch_ms
from features.api.routes.plugins.plugin_provider_delete_route import (
    provider_delete_external,
)
from features.api.routes.plugins.provider_lifecycle_operations import (
    ensure_external_provider_support,
    get_provider_for_plugin_or_raise,
)
from features.api.routes.plugins.provider_mutation_failure import (
    raise_provider_mutation_failure,
)
from features.api.routes.plugins.provider_mutation_headers import (
    require_provider_revision,
)
from features.api.routes.plugins.provider_update_outcome import (
    resolve_provider_update_outcome,
)
from features.api.runtime.access_dependencies import restart_protected_dependencies
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import (
    raise_conflict,
    raise_invalid_request,
    raise_not_found,
)
from features.api.runtime.external_provider_names import (
    has_external_provider_name_conflict,
)
from features.api.runtime.external_provider_save_validation import (
    evaluate_external_provider_discovery_skip,
    should_skip_external_provider_discovery,
    validate_external_provider_for_save,
)
from features.api.runtime.external_provider_update_inputs import (
    build_external_provider_update_validation_input,
)
from features.api.runtime.idempotency import require_idempotency_key
from features.api.schemas.plugins import ExternalProviderUpdate

__all__ = ("register_routes",)

OPERATION_API_PLUGIN_PROVIDER_UPDATE_EXTERNAL = "api_plugin.provider_update_external"


async def provider_update_external(
    request: Request,
    plugin_name: str,
    provider_id: str,
    payload: ExternalProviderUpdate,
    response: Response,
    api_context: ApiContext = Depends(resolve_api_context),
) -> ExternalProviderRecord:
    plugin_manager_instance = api_context.dependencies.plugin_manager
    try:
        operation_id = require_idempotency_key(request)
        expected_revision = require_provider_revision(request)
    except ValidationError as exception:
        raise_invalid_request(request, exception.message)
    update_data = payload.model_dump(exclude_unset=True, mode="json")
    if not update_data:
        raise_invalid_request(request, "No fields provided for update.")
    if "api_url" in update_data and update_data["api_url"] is None:
        raise_invalid_request(request, "api_url cannot be cleared.")
    canonical_plugin_name, _display_name = await ensure_external_provider_support(
        request,
        plugin_name,
        plugin_manager_instance,
    )
    owner_id = resolve_http_owner_id(request.state.context)
    updates_json = serialize_json_compact_stable_strict(update_data)
    replay = (
        await api_context.dependencies.model_provider_coordinator.provider_read_mutation_outcome(
            ProviderMutationReplayRequest(
                operation_id=operation_id,
                owner_id=owner_id,
                operation_type="update",
                plugin_name=canonical_plugin_name,
                provider_id=provider_id,
                expected_revision=expected_revision,
                request_json=updates_json,
            )
        )
    )
    if replay is not None:
        return resolve_provider_update_outcome(
            request,
            response,
            provider_id,
            canonical_plugin_name,
            replay[0],
            replay[1],
        )
    provider_record, canonical_plugin_name, display_name = await get_provider_for_plugin_or_raise(
        request,
        plugin_name,
        provider_id,
        api_context.dependencies.model_provider_coordinator,
        plugin_manager_instance,
    )
    needs_validation = any(
        field in update_data
        for field in (
            "api_url",
            "api_key",
            "extra_headers",
            "extra_query_params",
        )
    )
    validation = None
    if "name" in update_data:
        existing_providers = (
            await api_context.dependencies.model_provider_coordinator.provider_list_for_plugin(
                canonical_plugin_name,
            )
        )
        if has_external_provider_name_conflict(
            existing_providers,
            update_data.get("name"),
            ignored_provider_id=provider_id,
        ):
            raise_conflict(
                request,
                f"A provider with the name '{update_data['name']}' already exists.",
                error_type="conflict",
            )
    if needs_validation:
        existing_decrypted = (
            await api_context.dependencies.model_provider_coordinator.provider_get_external(
                provider_id,
                decrypt_key=True,
            )
        )
        if not existing_decrypted:
            raise_not_found(request, f"Provider with ID '{provider_id}' not found.")
        if existing_decrypted.get("plugin_name") != canonical_plugin_name:
            raise_not_found(request, f"Provider with ID '{provider_id}' not found.")
        validation_input = build_external_provider_update_validation_input(
            update_data,
            provider_record,
            existing_decrypted,
        )
        validation = await validate_external_provider_for_save(
            api_context.dependencies.runtime_flags,
            api_url=validation_input.api_url,
            api_key=validation_input.api_key,
            extra_headers=validation_input.extra_headers,
            extra_query_params=validation_input.extra_query_params,
            source="external provider update",
        )
        if not validation.ok:
            raise_invalid_request(
                request,
                validation.message,
                extra={"validation": validation.details},
            )
    else:
        validation = await evaluate_external_provider_discovery_skip(
            api_context.dependencies.runtime_flags,
            api_url=str(provider_record.get("api_url") or ""),
            source="external provider update discovery",
        )
    skip_discovery = validation is not None and should_skip_external_provider_discovery(validation)
    validated_at_ms: int | None
    if validation is not None and skip_discovery:
        validation_status = "UNCHECKED"
        validation_error = validation.message
        validated_at_ms = epoch_ms()
    elif needs_validation:
        validation_status = "OK"
        validation_error = None
        validated_at_ms = epoch_ms()
    else:
        validation_status = str(provider_record.get("last_status") or "UNCHECKED")
        validation_error_value = provider_record.get("last_error")
        validation_error = (
            validation_error_value if isinstance(validation_error_value, str) else None
        )
        validated_at_value = provider_record.get("last_checked_at_ms")
        validated_at_ms = validated_at_value if isinstance(validated_at_value, int) else None
    audit_details = sanitize_provider_audit(update_data)
    log_audit_event(
        request,
        "UPDATE_PROVIDER",
        provider_id,
        {
            "plugin": canonical_plugin_name,
            "display_name": display_name,
            "update_data": audit_details,
        },
    )
    try:
        mutation_outcome, updated_provider = (
            await api_context.dependencies.model_provider_coordinator.provider_update_external_v1(
                ProviderUpdateMutationRequest(
                    operation_id=operation_id,
                    owner_id=owner_id,
                    plugin_name=canonical_plugin_name,
                    provider_id=provider_id,
                    expected_revision=expected_revision,
                    updates_json=updates_json,
                    validation_status=validation_status,
                    validation_error=validation_error,
                    validated_at_ms=validated_at_ms,
                    accepted_at_ms=epoch_ms(),
                )
            )
        )
        return resolve_provider_update_outcome(
            request,
            response,
            provider_id,
            canonical_plugin_name,
            mutation_outcome,
            updated_provider,
        )
    except (ValidationError, ValueError, RuntimeError) as exception:
        raise_provider_mutation_failure(
            request,
            exception,
            operation=OPERATION_API_PLUGIN_PROVIDER_UPDATE_EXTERNAL,
            provider_id=provider_id,
            action="updating",
        )


def register_routes(routers: ApiRouters) -> None:
    routers.plugins.patch(
        "/{plugin_name}/providers/{provider_id}",
        status_code=200,
        dependencies=restart_protected_dependencies(AccessAction.PLUGIN_ADMIN),
    )(provider_update_external)
    routers.plugins.delete(
        "/{plugin_name}/providers/{provider_id}",
        status_code=204,
        dependencies=restart_protected_dependencies(AccessAction.PLUGIN_ADMIN),
    )(provider_delete_external)
