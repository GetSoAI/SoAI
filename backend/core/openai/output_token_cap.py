"""SoAI - Output token cap field family resolution and canonicalization [backend/core/openai/output_token_cap.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.validation.integers import is_non_negative_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "CANONICAL_OUTPUT_TOKEN_CAP_FIELD",
    "OUTPUT_TOKEN_CAP_ALIAS_FIELDS",
    "OUTPUT_TOKEN_CAP_FIELDS",
    "canonicalize_model_settings_output_token_cap",
    "resolve_output_token_cap",
)

CANONICAL_OUTPUT_TOKEN_CAP_FIELD = "max_completion_tokens"
OUTPUT_TOKEN_CAP_ALIAS_FIELDS: tuple[str, ...] = ("max_output_tokens", "max_tokens")
OUTPUT_TOKEN_CAP_FIELDS: tuple[str, ...] = (
    "max_output_tokens",
    "max_completion_tokens",
    "max_tokens",
)
_PARAMETERS_FIELD = "parameters"


def _collect_output_token_caps(
    payload: Mapping[str, JSONValue],
    field_names: tuple[str, ...],
) -> list[int]:
    caps: list[int] = []
    for field_name in field_names:
        value = payload.get(field_name)
        if is_non_negative_strict_int(value):
            caps.append(value)
    return caps


def resolve_output_token_cap(payload: Mapping[str, JSONValue]) -> int | None:
    caps = _collect_output_token_caps(payload, OUTPUT_TOKEN_CAP_FIELDS)
    if not caps:
        return None
    return min(caps)


def _has_output_token_cap_field(payload: Mapping[str, JSONValue]) -> bool:
    return any(field_name in payload for field_name in OUTPUT_TOKEN_CAP_FIELDS)


def _without_output_token_cap_fields(payload: Mapping[str, JSONValue]) -> JSONDict:
    return {key: value for key, value in payload.items() if key not in OUTPUT_TOKEN_CAP_FIELDS}


def _resolve_canonical_cap_value(
    *,
    model_settings: Mapping[str, JSONValue],
    parameters: Mapping[str, JSONValue] | None,
) -> JSONValue:
    if parameters is not None and CANONICAL_OUTPUT_TOKEN_CAP_FIELD in parameters:
        return parameters[CANONICAL_OUTPUT_TOKEN_CAP_FIELD]
    if CANONICAL_OUTPUT_TOKEN_CAP_FIELD in model_settings:
        return model_settings[CANONICAL_OUTPUT_TOKEN_CAP_FIELD]
    alias_caps = _collect_output_token_caps(model_settings, OUTPUT_TOKEN_CAP_ALIAS_FIELDS)
    if parameters is not None:
        alias_caps.extend(_collect_output_token_caps(parameters, OUTPUT_TOKEN_CAP_ALIAS_FIELDS))
    if not alias_caps:
        return None
    return min(alias_caps)


def canonicalize_model_settings_output_token_cap(model_settings: JSONDict) -> JSONDict:
    parameters_value = model_settings.get(_PARAMETERS_FIELD)
    parameters = parameters_value if isinstance(parameters_value, dict) else None
    parameters_carry_cap = parameters is not None and _has_output_token_cap_field(parameters)
    if not _has_output_token_cap_field(model_settings) and not parameters_carry_cap:
        return model_settings
    canonical_cap = _resolve_canonical_cap_value(
        model_settings=model_settings,
        parameters=parameters,
    )
    canonicalized = _without_output_token_cap_fields(model_settings)
    if parameters is None:
        canonicalized[CANONICAL_OUTPUT_TOKEN_CAP_FIELD] = canonical_cap
        return canonicalized
    canonicalized_parameters = _without_output_token_cap_fields(parameters)
    canonicalized_parameters[CANONICAL_OUTPUT_TOKEN_CAP_FIELD] = canonical_cap
    canonicalized[_PARAMETERS_FIELD] = canonicalized_parameters
    return canonicalized
