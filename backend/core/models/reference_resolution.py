"""SoAI - Shared model reference resolution primitives [backend/core/models/reference_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.models.model_info_fields import is_model_info_active_and_enabled
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.models.external_provider_record import ExternalProviderInternalRecord
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelResolutionServiceProtocol,
    )
    from core.orchestrator.routing_config import VirtualModelConfig
    from core.types.json import JSONDict

__all__ = (
    "ModelReferenceInfoRecord",
    "ResolvedModelReference",
    "collect_virtual_model_universal_ids",
    "load_model_info_record_pairs",
    "load_model_info_records",
    "resolve_context_window_tokens_for_reference",
    "resolve_model_reference",
)


@dataclass(frozen=True, slots=True)
class ResolvedModelReference:
    requested_name: str
    routing_key: str
    universal_ids: tuple[str, ...]
    is_virtual: bool
    is_enabled: bool = True


@dataclass(frozen=True, slots=True)
class ModelReferenceInfoRecord:
    universal_id: str
    model_info: JSONDict


def collect_virtual_model_universal_ids(
    virtual_model: VirtualModelConfig | None,
) -> tuple[str, ...]:
    if virtual_model is None:
        return ()
    universal_ids: list[str] = []
    for entry in virtual_model.models:
        universal_id = coerce_optional_trimmed_str(entry.universal_id)
        if universal_id is None:
            continue
        universal_ids.append(universal_id)
    return tuple(dict.fromkeys(universal_ids))


async def resolve_model_reference(
    *,
    model_name: str,
    model_resolution_service: ModelResolutionServiceProtocol,
    virtual_model_get: (
        Callable[[str], Awaitable[VirtualModelConfig | None] | VirtualModelConfig | None] | None
    ) = None,
) -> ResolvedModelReference | None:
    normalized_model_name = coerce_optional_trimmed_str(model_name)
    if normalized_model_name is None:
        return None
    if virtual_model_get is not None:
        virtual_model_result = virtual_model_get(normalized_model_name)
        virtual_model = (
            await virtual_model_result
            if inspect.isawaitable(virtual_model_result)
            else virtual_model_result
        )
        if virtual_model is not None:
            return ResolvedModelReference(
                requested_name=normalized_model_name,
                routing_key=normalized_model_name,
                universal_ids=collect_virtual_model_universal_ids(virtual_model),
                is_virtual=True,
                is_enabled=virtual_model.is_enabled,
            )
    universal_id = await model_resolution_service.model_resolve_to_universal_id(
        normalized_model_name,
    )
    if universal_id is None:
        return None
    return ResolvedModelReference(
        requested_name=normalized_model_name,
        routing_key=universal_id,
        universal_ids=(universal_id,),
        is_virtual=False,
        is_enabled=True,
    )


async def load_model_info_records(
    *,
    reference: ResolvedModelReference,
    model_information_service: ModelInformationServiceProtocol,
) -> tuple[JSONDict, ...] | None:
    record_pairs = await load_model_info_record_pairs(
        reference=reference,
        model_information_service=model_information_service,
    )
    if record_pairs is None or len(record_pairs) != len(reference.universal_ids):
        return None
    return tuple(record.model_info for record in record_pairs)


async def load_model_info_record_pairs(
    *,
    reference: ResolvedModelReference,
    model_information_service: ModelInformationServiceProtocol,
) -> tuple[ModelReferenceInfoRecord, ...] | None:
    if not reference.universal_ids:
        return ()
    if len(reference.universal_ids) == 1:
        record = await model_information_service.model_get_info(reference.universal_ids[0])
        if not isinstance(record, dict):
            return None
        return (
            ModelReferenceInfoRecord(
                universal_id=reference.universal_ids[0],
                model_info=record,
            ),
        )
    records_by_universal_id = await model_information_service.model_get_info_batch(
        list(reference.universal_ids),
    )
    if not isinstance(records_by_universal_id, dict):
        return None
    records: list[ModelReferenceInfoRecord] = []
    for universal_id in reference.universal_ids:
        record = records_by_universal_id.get(universal_id)
        if isinstance(record, dict):
            records.append(
                ModelReferenceInfoRecord(
                    universal_id=universal_id,
                    model_info=record,
                ),
            )
    return tuple(records)


def _record_pairs_match_reference_order(
    *,
    reference: ResolvedModelReference,
    record_pairs: tuple[ModelReferenceInfoRecord, ...],
) -> bool:
    positions_by_universal_id = {
        universal_id: index for index, universal_id in enumerate(reference.universal_ids)
    }
    previous_position = -1
    seen_positions: set[int] = set()
    for record in record_pairs:
        position = positions_by_universal_id.get(record.universal_id)
        if position is None or position in seen_positions:
            return False
        if position <= previous_position:
            return False
        seen_positions.add(position)
        previous_position = position
    return True


async def resolve_context_window_tokens_for_reference(
    *,
    reference: ResolvedModelReference,
    model_information_service: ModelInformationServiceProtocol,
    model_records: tuple[JSONDict, ...] | None = None,
    model_record_pairs: tuple[ModelReferenceInfoRecord, ...] | None = None,
    provider_records: tuple[ExternalProviderInternalRecord | JSONDict | None, ...] | None = None,
) -> int | None:
    if not reference.universal_ids:
        return None
    if provider_records is not None and len(provider_records) != len(reference.universal_ids):
        return None
    if model_records is not None and model_record_pairs is not None:
        return None
    if model_record_pairs is not None:
        if not _record_pairs_match_reference_order(
            reference=reference,
            record_pairs=model_record_pairs,
        ):
            return None
        record_pairs = model_record_pairs
    elif model_records is not None:
        if len(model_records) != len(reference.universal_ids):
            return None
        record_pairs = tuple(
            ModelReferenceInfoRecord(
                universal_id=universal_id,
                model_info=model_record,
            )
            for universal_id, model_record in zip(
                reference.universal_ids,
                model_records,
                strict=True,
            )
        )
    else:
        loaded_record_pairs = await load_model_info_record_pairs(
            reference=reference,
            model_information_service=model_information_service,
        )
        if loaded_record_pairs is None:
            return None
        record_pairs = loaded_record_pairs
    if not record_pairs:
        return None
    provider_records_by_universal_id: dict[
        str,
        ExternalProviderInternalRecord | JSONDict | None,
    ] = {}
    if provider_records is not None:
        provider_records_by_universal_id = dict(
            zip(reference.universal_ids, provider_records, strict=True),
        )
    resolved_tokens: list[int] = []
    for record in record_pairs:
        if not is_model_info_active_and_enabled(record.model_info):
            continue
        context_window_tokens = await model_information_service.model_resolve_context_window(
            record.universal_id,
            model_info=record.model_info,
            provider_record=provider_records_by_universal_id.get(record.universal_id),
            provider_record_resolved=provider_records is not None,
        )
        if isinstance(context_window_tokens, int) and context_window_tokens > 0:
            resolved_tokens.append(context_window_tokens)
    return min(resolved_tokens) if resolved_tokens else None
