"""SoAI - Shared model reference validation [backend/core/models/reference_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.models.model_info_fields import is_model_info_active_and_enabled
from core.models.reference_resolution import (
    load_model_info_records,
    resolve_model_reference,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelResolutionServiceProtocol,
    )
    from core.orchestrator.routing_config import VirtualModelConfig

__all__ = (
    "ValidatedModelReference",
    "validate_active_model_reference",
)


@dataclass(frozen=True, slots=True)
class ValidatedModelReference:
    requested_name: str
    routing_key: str
    universal_ids: tuple[str, ...]
    is_virtual: bool


async def validate_active_model_reference(
    *,
    model_name: str,
    model_resolution_service: ModelResolutionServiceProtocol,
    model_information_service: ModelInformationServiceProtocol,
    virtual_model_get: (
        Callable[[str], Awaitable[VirtualModelConfig | None] | VirtualModelConfig | None] | None
    ),
    unknown_message: str,
    disabled_message: str,
    details: dict[str, str] | None = None,
) -> ValidatedModelReference:
    reference = await resolve_model_reference(
        model_name=model_name,
        model_resolution_service=model_resolution_service,
        virtual_model_get=virtual_model_get,
    )
    if reference is None:
        raise ValidationError(unknown_message, details=details)
    if reference.is_virtual:
        if not reference.is_enabled:
            raise ValidationError(disabled_message, details=details)
        return await _validate_virtual_reference(
            reference_requested_name=reference.requested_name,
            reference_routing_key=reference.routing_key,
            reference_universal_ids=reference.universal_ids,
            model_information_service=model_information_service,
            unknown_message=unknown_message,
            disabled_message=disabled_message,
            details=details,
        )
    model_infos = await load_model_info_records(
        reference=reference,
        model_information_service=model_information_service,
    )
    if model_infos is None or not model_infos:
        raise ValidationError(unknown_message, details=details)
    if not is_model_info_active_and_enabled(model_infos[0]):
        raise ValidationError(disabled_message, details=details)
    return ValidatedModelReference(
        requested_name=reference.requested_name,
        routing_key=reference.routing_key,
        universal_ids=reference.universal_ids,
        is_virtual=False,
    )


async def _validate_virtual_reference(
    *,
    reference_requested_name: str,
    reference_routing_key: str,
    reference_universal_ids: tuple[str, ...],
    model_information_service: ModelInformationServiceProtocol,
    unknown_message: str,
    disabled_message: str,
    details: dict[str, str] | None,
) -> ValidatedModelReference:
    if not reference_universal_ids:
        raise ValidationError(unknown_message, details=details)
    records_by_universal_id = await model_information_service.model_get_info_batch(
        list(reference_universal_ids),
    )
    if not isinstance(records_by_universal_id, dict):
        raise ValidationError(unknown_message, details=details)
    any_record = False
    for universal_id in reference_universal_ids:
        model_info = records_by_universal_id.get(universal_id)
        if not isinstance(model_info, dict):
            continue
        any_record = True
        if is_model_info_active_and_enabled(model_info):
            return ValidatedModelReference(
                requested_name=reference_requested_name,
                routing_key=reference_routing_key,
                universal_ids=reference_universal_ids,
                is_virtual=True,
            )
    if any_record:
        raise ValidationError(disabled_message, details=details)
    raise ValidationError(unknown_message, details=details)
