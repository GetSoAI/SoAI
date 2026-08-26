"""SoAI - External provider lifecycle operations [backend/features/api/routes/plugins/provider_lifecycle_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import JSONResponse

from core.database.provider_mutation_requests import (
    ProviderCreateMutationRequest,
    ProviderMutationReplayRequest,
)
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.models.external_provider_public_projection import (
    coerce_external_provider_record,
    sanitize_provider_audit,
)
from core.models.external_provider_record import (
    ExternalProviderRecord,
    build_external_provider_id,
)
from core.models.protocols import ModelProviderCoordinatorProtocol
from core.plugins.errors import PluginCapabilityError
from core.plugins.protocols import PluginManagerProtocol
from core.runtime.ownership import resolve_http_owner_id
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.serialization.json import (
    normalize_for_json,
    serialize_json_compact_stable_strict,
)
from core.state.errors import DuplicateProviderError
from core.timing.epoch import epoch_ms
from core.types.json_value import coerce_json_dict
from features.api.routes.plugins.provider_create_response import (
    build_provider_create_response,
)
from features.api.runtime.audit import log_audit_event
from features.api.runtime.errors import (
    raise_action_not_supported,
    raise_conflict,
    raise_invalid_request,
    raise_not_found,
    raise_server_error,
)
from features.api.runtime.external_provider_names import (
    has_external_provider_name_conflict,
)
from features.api.runtime.external_provider_save_validation import (
    should_skip_external_provider_discovery,
    validate_external_provider_for_save,
)
from features.api.runtime.idempotency import require_idempotency_key
from features.api.runtime.plugin_compatibility import ensure_plugin_compatible_or_raise
from features.api.schemas.plugins import ExternalProviderCreate

if TYPE_CHECKING:
    from core.models.external_provider_record import ExternalProviderInternalRecord
    from core.types.json import JSONDict

__all__ = (
    "coerce_provider_record_or_server_error",
    "create_external_provider",
    "ensure_external_provider_support",
    "get_provider_for_plugin_or_raise",
)

LOGGER_NAME = "SoAI.features.api.provider_lifecycle_operations"
OPERATION = "api_plugin.create_external_provider"


async def ensure_external_provider_support(
    request: Request,
    plugin_name: str,
    plugin_manager_instance: PluginManagerProtocol,
) -> tuple[str, str]:
    await plugin_manager_instance.require_ready()
    normalized_plugin_name = plugin_name.strip()
    if not normalized_plugin_name:
        raise_invalid_request(request, "Plugin name is required.")
    canonical_plugin_name = plugin_manager_instance.normalize_plugin_name(normalized_plugin_name)
    if canonical_plugin_name is None:
        raise_not_found(request, f"Plugin '{normalized_plugin_name}' not found.")
    await ensure_plugin_compatible_or_raise(
        request,
        plugin_manager_instance,
        canonical_plugin_name,
    )
    try:
        await plugin_manager_instance.ensure_plugin_capability(
            canonical_plugin_name,
            "SUPPORTS_EXTERNAL_PROVIDERS",
            "External Providers",
        )
    except PluginCapabilityError as exception:
        raise_action_not_supported(request, str(exception))
    display_name = await plugin_manager_instance.get_plugin_display_name(canonical_plugin_name)
    return (canonical_plugin_name, display_name)


def coerce_provider_record_or_server_error(
    request: Request,
    provider: ExternalProviderInternalRecord | JSONDict,
    *,
    label: str,
) -> ExternalProviderRecord:
    try:
        coerced = coerce_json_dict(normalize_for_json(provider))
        if coerced is None:
            raise ValidationError(f"{label} is not a JSON object.")
        return coerce_external_provider_record(coerced, label=label)
    except ValidationError as exception:
        raise_server_error(request, str(exception))


async def get_provider_for_plugin_or_raise(
    request: Request,
    plugin_name: str,
    provider_id: str,
    model_provider_coordinator: ModelProviderCoordinatorProtocol,
    plugin_manager_instance: PluginManagerProtocol,
) -> tuple[ExternalProviderRecord, str, str]:
    canonical_plugin_name, display_name = await ensure_external_provider_support(
        request,
        plugin_name,
        plugin_manager_instance,
    )
    missing_message = f"Provider '{provider_id}' not found for plugin '{display_name}'."
    provider_info = await model_provider_coordinator.provider_get_external(provider_id)
    if not provider_info:
        raise_not_found(request, missing_message)
    provider_record = coerce_provider_record_or_server_error(
        request,
        provider_info,
        label="External provider record",
    )
    if provider_record["plugin_name"] != canonical_plugin_name:
        raise_not_found(request, missing_message)
    return (provider_record, canonical_plugin_name, display_name)


async def create_external_provider(
    request: Request,
    plugin_name: str,
    payload: ExternalProviderCreate,
    model_provider_coordinator: ModelProviderCoordinatorProtocol,
    plugin_manager_instance: PluginManagerProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
) -> JSONResponse:
    try:
        operation_id = require_idempotency_key(request)
    except ValidationError as exception:
        raise_invalid_request(request, exception.message)
    canonical_plugin_name, display_name = await ensure_external_provider_support(
        request,
        plugin_name,
        plugin_manager_instance,
    )
    owner_id = resolve_http_owner_id(request.state.context)
    try:
        provider_id = build_external_provider_id(canonical_plugin_name, str(payload.api_url))
        provider_json = serialize_json_compact_stable_strict(
            payload.model_dump(mode="json", exclude_none=True)
        )
        replay = await model_provider_coordinator.provider_read_mutation_outcome(
            ProviderMutationReplayRequest(
                operation_id=operation_id,
                owner_id=owner_id,
                operation_type="create",
                plugin_name=canonical_plugin_name,
                provider_id=provider_id,
                expected_revision=0,
                request_json=provider_json,
            )
        )
        if replay is not None:
            replay_outcome, replay_provider = replay
            if replay_outcome.outcome == "conflict":
                raise_conflict(
                    request,
                    "A provider with the same identity, URL, or name already exists.",
                    error_type="conflict",
                )
            if replay_provider is None:
                raise_server_error(request, "Provider replay projection is unavailable.")
            replay_record = coerce_provider_record_or_server_error(
                request,
                replay_provider,
                label="External provider replay record",
            )
            return build_provider_create_response(replay_record, {})
        audit_details = sanitize_provider_audit(payload.model_dump(mode="json"))
        log_audit_event(
            request,
            "CREATE_PROVIDER",
            canonical_plugin_name,
            {"display_name": display_name, "provider_details": audit_details},
        )
        if payload.name:
            existing = await model_provider_coordinator.provider_list_for_plugin(
                canonical_plugin_name,
            )
            if has_external_provider_name_conflict(
                existing,
                payload.name,
                ignored_provider_id=provider_id,
            ):
                raise_conflict(
                    request,
                    f"A provider with the name '{payload.name}' already exists.",
                    error_type="conflict",
                )
        validation = await validate_external_provider_for_save(
            runtime_flags,
            api_url=str(payload.api_url),
            api_key=payload.api_key,
            extra_headers=payload.extra_headers,
            extra_query_params=payload.extra_query_params,
            source="external provider creation",
        )
        if not validation.ok:
            raise_invalid_request(
                request, validation.message, extra={"validation": validation.details}
            )
        skip_discovery = should_skip_external_provider_discovery(validation)
        validation_status = "UNCHECKED" if skip_discovery else "OK"
        validation_error = validation.message if skip_discovery else None
        validated_at_ms = epoch_ms()
        mutation_outcome, provider = await model_provider_coordinator.provider_add_external_v1(
            ProviderCreateMutationRequest(
                operation_id=operation_id,
                owner_id=owner_id,
                plugin_name=canonical_plugin_name,
                provider_id=provider_id,
                provider_json=provider_json,
                validation_status=validation_status,
                validation_error=validation_error,
                validated_at_ms=validated_at_ms,
                accepted_at_ms=epoch_ms(),
            )
        )
        if mutation_outcome.outcome == "conflict":
            raise_conflict(
                request,
                "A provider with the same identity, URL, or name already exists.",
                error_type="conflict",
            )
        if not provider:
            raise_server_error(
                request,
                "Failed to create provider record in database.",
                error_type="create_failed",
            )
        provider_record = coerce_provider_record_or_server_error(
            request,
            provider,
            label="External provider record",
        )
        if provider_record["plugin_name"] != canonical_plugin_name:
            raise_server_error(request, "Created provider record is bound to the wrong plugin.")
        return build_provider_create_response(provider_record, validation.details)
    except DuplicateProviderError as exception:
        raise_conflict(request, str(exception), error_type="conflict")
    except (ValidationError, ValueError) as exception:
        raise_invalid_request(request, str(exception))
    except RECOVERABLE_EXCEPTIONS as exception:
        if isinstance(exception, SoAIError):
            raise
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Unexpected exception in create_provider_for_plugin",
            operation=OPERATION,
            details={"plugin": canonical_plugin_name},
        )
        raise_server_error(request, str(exception))
