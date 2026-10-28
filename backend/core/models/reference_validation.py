"""SoAI - Shared model reference validation [backend/core/models/reference_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.errors.model_reference_error import ModelReferenceNotFoundError
from core.models.model_info_fields import is_model_info_active_and_enabled
from core.models.reference_resolution import (
    load_model_info_records,
    resolve_model_reference,
)
from core.openai.capability_checks import is_openai_model_capability_supported

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelResolutionServiceProtocol,
    )
    from core.orchestrator.routing_config import VirtualModelConfig
    from core.types.json import JSONDict

__all__ = (
    "RequiredModelCapability",
    "ValidatedModelReference",
    "validate_active_model_reference",
)


@dataclass(frozen=True, slots=True)
class ValidatedModelReference:
    requested_name: str
    routing_key: str
    universal_ids: tuple[str, ...]
    is_virtual: bool


@dataclass(frozen=True, slots=True)
class RequiredModelCapability:
    token: str
    unsupported_message: str


@dataclass(frozen=True, slots=True)
class _ModelReferenceMessages:
    unknown_message: str
    disabled_message: str
    details: dict[str, str] | None


def _supports_required_capability(
    model_info: JSONDict,
    required_capability: RequiredModelCapability | None,
) -> bool:
    if required_capability is None:
        return True
    return is_openai_model_capability_supported(model_info, required_capability.token)


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
    required_capability: RequiredModelCapability | None,
    details: dict[str, str] | None = None,
) -> ValidatedModelReference:
    messages = _ModelReferenceMessages(
        unknown_message=unknown_message,
        disabled_message=disabled_message,
        details=details,
    )
    reference = await resolve_model_reference(
        model_name=model_name,
        model_resolution_service=model_resolution_service,
        virtual_model_get=virtual_model_get,
    )
    if reference is None:
        raise ModelReferenceNotFoundError(unknown_message, details=details)
    if reference.is_virtual:
        if not reference.is_enabled:
            raise ValidationError(disabled_message, details=details)
        await _validate_virtual_reference(
            reference_universal_ids=reference.universal_ids,
            model_information_service=model_information_service,
            messages=messages,
            required_capability=required_capability,
        )
        return ValidatedModelReference(
            requested_name=reference.requested_name,
            routing_key=reference.routing_key,
            universal_ids=reference.universal_ids,
            is_virtual=True,
        )
    model_infos = await load_model_info_records(
        reference=reference,
        model_information_service=model_information_service,
    )
    if model_infos is None or not model_infos:
        raise ValidationError(unknown_message, details=details)
    model_info = model_infos[0]
    if not is_model_info_active_and_enabled(model_info):
        raise ValidationError(disabled_message, details=details)
    if required_capability is not None and not is_openai_model_capability_supported(
        model_info,
        required_capability.token,
    ):
        raise ValidationError(required_capability.unsupported_message, details=details)
    return ValidatedModelReference(
        requested_name=reference.requested_name,
        routing_key=reference.routing_key,
        universal_ids=reference.universal_ids,
        is_virtual=False,
    )


async def _validate_virtual_reference(
    *,
    reference_universal_ids: tuple[str, ...],
    model_information_service: ModelInformationServiceProtocol,
    messages: _ModelReferenceMessages,
    required_capability: RequiredModelCapability | None,
) -> None:
    if not reference_universal_ids:
        raise ValidationError(messages.unknown_message, details=messages.details)
    records_by_universal_id = await model_information_service.model_get_info_batch(
        list(reference_universal_ids),
    )
    if not isinstance(records_by_universal_id, dict):
        raise ValidationError(messages.unknown_message, details=messages.details)
    any_record = False
    any_active = False
    for universal_id in reference_universal_ids:
        model_info = records_by_universal_id.get(universal_id)
        if not isinstance(model_info, dict):
            continue
        any_record = True
        if not is_model_info_active_and_enabled(model_info):
            continue
        any_active = True
        if _supports_required_capability(model_info, required_capability):
            return
    if any_active and required_capability is not None:
        raise ValidationError(required_capability.unsupported_message, details=messages.details)
    if any_record:
        raise ValidationError(messages.disabled_message, details=messages.details)
    raise ValidationError(messages.unknown_message, details=messages.details)
