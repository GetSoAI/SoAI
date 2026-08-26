"""SoAI - OpenAI token estimation profile resolution [backend/features/openai/token_estimation_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

import tiktoken

from core.models.model_info_fields import is_model_info_active_and_enabled
from core.openai.token_counter_types import (
    APPROXIMATE_CHARS_PER_TOKEN_FLOOR,
    APPROXIMATE_TOKEN_ENCODING_NAME,
)
from core.openai.token_estimation_profile import TokenEstimationProfile
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.models.external_provider_record import (
        ExternalProviderInternalRecord,
        ExternalProviderRecord,
    )
    from core.types.json import JSONDict, JSONValue

__all__ = ("resolve_token_estimation_profile",)


def _resolve_known_model_encoding_name(model_name: str) -> str | None:
    try:
        return tiktoken.encoding_for_model(model_name).name
    except KeyError:
        return None


def _iter_json_text_values(
    payload: Mapping[str, JSONValue] | None,
    keys: tuple[str, ...],
) -> Iterable[str]:
    if not isinstance(payload, Mapping):
        return ()
    values: list[str] = []
    for key in keys:
        value = coerce_optional_trimmed_str(payload.get(key))
        if value is not None:
            values.append(value)
    return tuple(values)


def _iter_model_record_candidates(record: JSONDict) -> Iterable[str]:
    source_model_id = coerce_optional_trimmed_str(record.get("source_model_id"))
    if source_model_id is not None:
        return (source_model_id,)
    values: list[str] = []
    values.extend(
        _iter_json_text_values(
            record,
            ("id", "model", "name", "model_id", "root"),
        ),
    )
    for nested_key in ("model_metadata", "metadata", "details"):
        nested = record.get(nested_key)
        if isinstance(nested, dict):
            values.extend(_iter_json_text_values(nested, ("id", "model", "name", "root")))
    return tuple(values)


def _iter_normalized_model_record_candidates(record: JSONDict) -> Iterable[str]:
    values: list[str] = []
    for candidate in _iter_model_record_candidates(record):
        values.extend(_iter_normalized_model_candidates(candidate))
    return tuple(dict.fromkeys(values))


def _iter_provider_candidates(
    provider_record: ExternalProviderRecord | ExternalProviderInternalRecord | JSONDict | None,
) -> Iterable[str]:
    if provider_record is None:
        return ()
    values: list[str] = []
    for key in ("model", "model_id", "tokenizer_model", "tokenizer_model_id"):
        value = provider_record.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
    return tuple(values)


def _iter_normalized_model_candidates(model_name: str) -> Iterable[str]:
    normalized = coerce_optional_trimmed_str(model_name)
    if normalized is None:
        return ()
    values = [normalized]
    if "/" in normalized:
        values.append(normalized.rsplit("/", 1)[-1])
    for value in tuple(values):
        if ":" in value:
            values.append(value.replace(":", "-"))
    return tuple(dict.fromkeys(values))


def _resolve_known_encoding_from_candidates(candidates: Iterable[str]) -> str | None:
    for candidate in dict.fromkeys(candidates):
        encoding_name = _resolve_known_model_encoding_name(candidate)
        if encoding_name is not None:
            return encoding_name
    return None


def _resolve_shared_model_records_encoding(model_records: tuple[JSONDict, ...]) -> str | None:
    if not model_records or not all(
        is_model_info_active_and_enabled(record) for record in model_records
    ):
        return None
    encoding_names: list[str] = []
    for record in model_records:
        encoding_name = _resolve_known_encoding_from_candidates(
            _iter_normalized_model_record_candidates(record),
        )
        if encoding_name is None:
            return None
        encoding_names.append(encoding_name)
    shared = tuple(dict.fromkeys(encoding_names))
    return shared[0] if len(shared) == 1 else None


def _build_approximate_profile() -> TokenEstimationProfile:
    return TokenEstimationProfile.approximate(
        encoding_name=APPROXIMATE_TOKEN_ENCODING_NAME,
        chars_per_token_floor=APPROXIMATE_CHARS_PER_TOKEN_FLOOR,
    )


def resolve_token_estimation_profile(
    *,
    model_name: str,
    provider_record: ExternalProviderRecord | ExternalProviderInternalRecord | JSONDict | None,
    model_records: tuple[JSONDict, ...] | None = None,
) -> TokenEstimationProfile:
    if model_records is not None:
        if len(model_records) > 1:
            shared_encoding = _resolve_shared_model_records_encoding(model_records)
            if shared_encoding is not None:
                return TokenEstimationProfile.exact(shared_encoding)
            return _build_approximate_profile()
        if len(model_records) == 1:
            model_record = model_records[0]
            if not is_model_info_active_and_enabled(model_record):
                return _build_approximate_profile()
            record_candidates = list(_iter_normalized_model_record_candidates(model_record))
            for candidate in _iter_provider_candidates(provider_record):
                record_candidates.extend(_iter_normalized_model_candidates(candidate))
            encoding_name = _resolve_known_encoding_from_candidates(record_candidates)
            if encoding_name is not None:
                return TokenEstimationProfile.exact(encoding_name)
        return _build_approximate_profile()
    provider_candidates = tuple(_iter_provider_candidates(provider_record))
    candidates: list[str] = []
    for candidate in provider_candidates:
        candidates.extend(_iter_normalized_model_candidates(candidate))
    if not provider_candidates:
        candidates.extend(_iter_normalized_model_candidates(model_name))
    encoding_name = _resolve_known_encoding_from_candidates(candidates)
    if encoding_name is not None:
        return TokenEstimationProfile.exact(encoding_name)
    return _build_approximate_profile()
