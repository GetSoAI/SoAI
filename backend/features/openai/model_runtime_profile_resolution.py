"""SoAI - OpenAI model runtime profile resolution [backend/features/openai/model_runtime_profile_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.models.reference_resolution import (
    load_model_info_record_pairs,
    resolve_context_window_tokens_for_reference,
    resolve_model_reference,
)
from core.openai.token_estimation_profile import TokenEstimationProfile
from core.validation.strings import coerce_optional_trimmed_str
from features.openai.context_window_defaults import (
    resolve_default_openai_context_window_tokens,
)
from features.openai.token_estimation_resolution import resolve_token_estimation_profile

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.models.external_provider_record import ExternalProviderInternalRecord
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelResolutionServiceProtocol,
    )
    from core.models.reference_resolution import ModelReferenceInfoRecord, ResolvedModelReference
    from core.orchestrator.routing_config import VirtualModelConfig
    from core.types.json import JSONDict

__all__ = (
    "OpenAIModelRuntimeProfile",
    "resolve_openai_model_runtime_profile",
)


@dataclass(frozen=True, slots=True)
class OpenAIModelRuntimeProfile:
    context_window_tokens: int
    context_window_unverified: bool
    token_estimation_profile: TokenEstimationProfile
    reference: ResolvedModelReference | None = None
    model_records: tuple[JSONDict, ...] | None = None


async def _resolve_provider_records(
    *,
    reference: ResolvedModelReference,
    model_records: tuple[ModelReferenceInfoRecord, ...],
    provider_get_external: Callable[[str, bool], Awaitable[ExternalProviderInternalRecord | None]],
) -> tuple[ExternalProviderInternalRecord | None, ...]:
    provider_ids_by_universal_id: dict[str, str] = {}
    for record in model_records:
        provider_id = coerce_optional_trimmed_str(record.model_info.get("provider_id"))
        if provider_id is not None:
            provider_ids_by_universal_id[record.universal_id] = provider_id
    provider_ids = tuple(
        dict.fromkeys(provider_ids_by_universal_id.values()),
    )
    if not provider_ids:
        return tuple(None for _universal_id in reference.universal_ids)
    provider_tasks = [provider_get_external(provider_id, False) for provider_id in provider_ids]
    provider_results = await asyncio.gather(
        *provider_tasks,
        return_exceptions=False,
    )
    providers_by_id = dict(zip(provider_ids, provider_results, strict=True))
    resolved: list[ExternalProviderInternalRecord | None] = []
    for universal_id in reference.universal_ids:
        provider_id = provider_ids_by_universal_id.get(universal_id)
        resolved.append(providers_by_id.get(provider_id) if provider_id is not None else None)
    return tuple(resolved)


def _strict_records_from_pairs(
    *,
    reference: ResolvedModelReference,
    model_records: tuple[ModelReferenceInfoRecord, ...],
) -> tuple[JSONDict, ...] | None:
    if len(model_records) != len(reference.universal_ids):
        return None
    for universal_id, model_record in zip(reference.universal_ids, model_records, strict=True):
        if universal_id != model_record.universal_id:
            return None
    return tuple(record.model_info for record in model_records)


async def resolve_openai_model_runtime_profile(
    *,
    config: ConfigProtocol,
    model_name: str,
    model_resolution_service: ModelResolutionServiceProtocol,
    model_information_service: ModelInformationServiceProtocol,
    provider_get_external: Callable[[str, bool], Awaitable[ExternalProviderInternalRecord | None]],
    virtual_model_get: (
        Callable[[str], Awaitable[VirtualModelConfig | None] | VirtualModelConfig | None] | None
    ) = None,
) -> OpenAIModelRuntimeProfile:
    reference = await resolve_model_reference(
        model_name=model_name,
        model_resolution_service=model_resolution_service,
        virtual_model_get=virtual_model_get,
    )
    context_window_tokens: int | None = None
    records: tuple[JSONDict, ...] | None = None
    provider_records: tuple[ExternalProviderInternalRecord | None, ...] | None = None
    if reference is not None:
        record_pairs = await load_model_info_record_pairs(
            reference=reference,
            model_information_service=model_information_service,
        )
        if record_pairs is not None:
            records = _strict_records_from_pairs(reference=reference, model_records=record_pairs)
            provider_records = await _resolve_provider_records(
                reference=reference,
                model_records=record_pairs,
                provider_get_external=provider_get_external,
            )
            context_window_tokens = await resolve_context_window_tokens_for_reference(
                reference=reference,
                model_information_service=model_information_service,
                model_record_pairs=record_pairs,
                provider_records=provider_records,
            )
    context_window_unverified = context_window_tokens is None
    if context_window_tokens is None:
        context_window_tokens = resolve_default_openai_context_window_tokens(config)
    provider_record = None
    if provider_records is not None and len(provider_records) == 1:
        provider_record = provider_records[0]
    token_profile = resolve_token_estimation_profile(
        model_name=model_name,
        provider_record=provider_record,
        model_records=records,
    )
    return OpenAIModelRuntimeProfile(
        context_window_tokens=context_window_tokens,
        context_window_unverified=context_window_unverified,
        token_estimation_profile=token_profile,
        reference=reference,
        model_records=records,
    )
