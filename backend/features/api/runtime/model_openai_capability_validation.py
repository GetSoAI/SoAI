"""SoAI - OpenAI capability validation for a model ID [backend/features/api/runtime/model_openai_capability_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.models.model_info_fields import is_model_info_active_and_enabled
from core.models.reference_errors import UnknownModelReferenceError
from core.models.reference_resolution import (
    load_model_info_records,
    resolve_model_reference,
)
from core.openai.capability_checks import is_openai_model_capability_enabled
from core.openai.capability_taxonomy import OPENAI_CAPABILITY_CATEGORIES
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelResolutionServiceProtocol,
    )
    from core.orchestrator.routing_config import VirtualModelConfig
    from core.types.json import JSONDict

__all__ = ("require_openai_capability_for_model",)


def _model_supports_capability(model_info: JSONDict, capability_key: str) -> bool:
    return any(
        is_openai_model_capability_enabled(
            model_info,
            category=category,
            token=capability_key,
        )
        for category in OPENAI_CAPABILITY_CATEGORIES
    )


async def _require_virtual_model_capability(
    *,
    universal_ids: tuple[str, ...],
    requested_name: str,
    label_prefix: str,
    capability_key: str,
    model_information_service: ModelInformationServiceProtocol,
) -> None:
    if not universal_ids:
        raise UnknownModelReferenceError(f"{label_prefix}unknown model: {requested_name}")
    records_by_universal_id = await model_information_service.model_get_info_batch(
        list(universal_ids),
    )
    any_record = False
    any_enabled = False
    for universal_id in universal_ids:
        model_info = records_by_universal_id.get(universal_id)
        if model_info is None:
            continue
        any_record = True
        if not is_model_info_active_and_enabled(model_info):
            continue
        any_enabled = True
        if _model_supports_capability(model_info, capability_key):
            return
    if any_enabled:
        raise ValidationError(
            f"{label_prefix}model does not support {capability_key}: {requested_name}",
        )
    if any_record:
        raise ValidationError(f"{label_prefix}model is disabled: {requested_name}")
    raise UnknownModelReferenceError(f"{label_prefix}unknown model: {requested_name}")


async def require_openai_capability_for_model(
    *,
    model_resolution_service: ModelResolutionServiceProtocol,
    model_information_service: ModelInformationServiceProtocol,
    virtual_model_get: (
        Callable[[str], Awaitable[VirtualModelConfig | None] | VirtualModelConfig | None] | None
    ),
    model_name: str,
    capability_key: str,
    label: str,
) -> str:
    normalized_label = label.strip()
    label_prefix = f"{normalized_label}: " if normalized_label else ""
    normalized_model_name = coerce_optional_trimmed_str(model_name)
    if normalized_model_name is None:
        raise UnknownModelReferenceError(f"{label_prefix}model is required.")
    reference = await resolve_model_reference(
        model_name=normalized_model_name,
        model_resolution_service=model_resolution_service,
        virtual_model_get=virtual_model_get,
    )
    if reference is None:
        raise UnknownModelReferenceError(f"{label_prefix}unknown model: {normalized_model_name}")
    if reference.is_virtual:
        if not reference.is_enabled:
            raise ValidationError(f"{label_prefix}model is disabled: {reference.requested_name}")
        await _require_virtual_model_capability(
            universal_ids=reference.universal_ids,
            requested_name=reference.requested_name,
            label_prefix=label_prefix,
            capability_key=capability_key,
            model_information_service=model_information_service,
        )
        return reference.routing_key
    model_infos = await load_model_info_records(
        reference=reference,
        model_information_service=model_information_service,
    )
    if model_infos is None or not model_infos:
        raise UnknownModelReferenceError(f"{label_prefix}unknown model: {reference.requested_name}")
    model_info = model_infos[0]
    if not is_model_info_active_and_enabled(model_info):
        raise ValidationError(f"{label_prefix}model is disabled: {reference.requested_name}")
    if not _model_supports_capability(model_info, capability_key):
        raise ValidationError(
            f"{label_prefix}model does not support {capability_key}: {reference.requested_name}",
        )
    return reference.routing_key
