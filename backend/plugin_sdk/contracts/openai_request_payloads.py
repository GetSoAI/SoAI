"""SoAI - Plugin SDK OpenAI request payload shaping [backend/plugin_sdk/contracts/openai_request_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.logging.trace import get_logger
from core.openai.endpoint_request_contracts import (
    OpenAIRequestBodyOperation,
    contract_for_openai_request_body_operation,
)
from core.openai.upstream_request_customization import (
    SOAI_INTERNAL_OPENAI_REQUEST_KEYS,
    resolve_openai_upstream_request_customization,
)
from core.types.json import JSONDict
from core.types.json_value import copy_json_value

__all__ = (
    "OpenAIRequestBodyOperation",
    "build_openai_upstream_request_body_payload",
    "resolve_openai_upstream_custom_request_field_names",
)

_LOGGER_NAME = "SoAI.plugin_sdk.contracts.openai_request_payloads"
_DROPPED_KEY_LOG_CAP = 25


def _emit_dropped_fields_warning(
    *,
    operation: OpenAIRequestBodyOperation,
    dropped_from_model_parameters: set[str],
    dropped_from_request_json: set[str],
) -> None:
    if not dropped_from_model_parameters and not dropped_from_request_json:
        return
    logger = get_logger(_LOGGER_NAME)
    dropped_all = dropped_from_model_parameters | dropped_from_request_json
    ordered_all = sorted(dropped_all)
    capped_all = ordered_all[:_DROPPED_KEY_LOG_CAP]
    extra_count = len(ordered_all) - len(capped_all)
    dropped_keys = ", ".join(capped_all) + (f", ... (+{extra_count})" if extra_count else "")
    sources: list[str] = []
    if dropped_from_request_json:
        sources.append("request_json")
    if dropped_from_model_parameters:
        sources.append("model_parameters")
    logger.warning(
        "Dropped non-contract OpenAI request fields for operation '%s' from %s: %s",
        operation.value,
        "+".join(sources),
        dropped_keys,
    )


def build_openai_upstream_request_body_payload(
    *,
    operation: OpenAIRequestBodyOperation,
    source_model_id: str,
    request_json: JSONDict,
    model_parameters: JSONDict,
) -> JSONDict:
    contract = contract_for_openai_request_body_operation(operation)
    customization = resolve_openai_upstream_request_customization(model_parameters)
    payload: JSONDict = {"model": source_model_id}
    dropped_from_model_parameters: set[str] = set()
    dropped_from_request_json: set[str] = set()
    for source_name, source in (
        ("model_parameters", model_parameters),
        ("request_json", request_json),
    ):
        for key, value in source.items():
            if key == "model":
                continue
            if key in SOAI_INTERNAL_OPENAI_REQUEST_KEYS:
                continue
            if key in customization.excluded_fields:
                continue
            if key not in contract.official_fields:
                if source_name == "model_parameters":
                    dropped_from_model_parameters.add(key)
                else:
                    dropped_from_request_json.add(key)
                continue
            if value is None:
                continue
            payload[key] = copy_json_value(value)
    for key, value in customization.custom_fields.items():
        payload[key] = copy_json_value(value)
    for key in customization.excluded_fields:
        payload.pop(key, None)
    _emit_dropped_fields_warning(
        operation=operation,
        dropped_from_model_parameters=dropped_from_model_parameters,
        dropped_from_request_json=dropped_from_request_json,
    )
    return payload


def resolve_openai_upstream_custom_request_field_names(
    model_parameters: JSONDict,
) -> frozenset[str]:
    customization = resolve_openai_upstream_request_customization(model_parameters)
    return frozenset(customization.custom_fields)
