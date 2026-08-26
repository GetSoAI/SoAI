"""SoAI - Orchestration context persisted field parsing [backend/core/tasks/orchestration_context_persisted_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.orchestrator.request_priority import RequestPriority, RequestPriorityAssignment
from core.runtime.request_sources import normalize_request_source
from core.types.json import is_json_dict, is_str_list
from core.validation.integers import is_strict_int
from core.validation.record_fields import require_non_empty_str

if TYPE_CHECKING:
    from core.runtime.request_sources import RequestSource
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "OrchestrationContextPersistedFields",
    "deserialize_orchestration_context",
)


@dataclass(frozen=True, slots=True)
class OrchestrationContextPersistedFields:
    execution_universal_ids: tuple[str, ...]
    parameter_overrides: dict[str, dict[str, JSONValue]]
    parameter_snapshot: tuple[dict[str, JSONValue], int] | None
    virtual_model_name: str | None
    routing_key: str | None
    plugin_name: str | None
    request_payload: dict[str, JSONValue]
    request_event_type: str
    request_context_data: dict[str, JSONValue]
    required_capabilities: tuple[str, ...]
    required_modalities: tuple[str, ...]
    request_source: RequestSource
    delivery_mode: str
    startup_params: dict[str, JSONValue]
    inference_params: dict[str, JSONValue]
    parameter_version: int | None
    startup_param_fingerprint: str | None
    excluded_universal_ids: frozenset[str]
    dedup_hash: str | None
    dedup_lead_task_id: str | None
    tracking_id: str
    priority_assignment: RequestPriorityAssignment
    is_requeued: bool


def deserialize_orchestration_context(data: JSONDict) -> OrchestrationContextPersistedFields:
    if not data:
        raise ValidationError("Cannot create OrchestrationContext from empty data")
    tracking_id_value = data.get("tracking_id")
    tracking_id = tracking_id_value.strip() if isinstance(tracking_id_value, str) else ""
    if not tracking_id:
        raise ValidationError("Persisted orchestration context missing tracking_id.")
    queued_at_value = data.get("queued_at")
    if isinstance(queued_at_value, bool) or not isinstance(queued_at_value, int | float):
        raise ValidationError("Persisted orchestration context missing queued_at.")
    queued_at = float(queued_at_value)
    request_priority_value = data.get("request_priority")
    if not isinstance(request_priority_value, str):
        raise ValidationError("Persisted orchestration context has invalid request_priority.")
    try:
        request_priority = RequestPriority(request_priority_value)
    except ValueError as exception:
        raise ValidationError(
            "Persisted orchestration context has invalid request_priority."
        ) from exception
    priority_order_value = data.get("priority_order")
    if isinstance(priority_order_value, bool) or not isinstance(
        priority_order_value,
        int | float,
    ):
        raise ValidationError("Persisted orchestration context missing priority_order.")
    priority_order = float(priority_order_value)
    is_requeued_value = data.get("is_requeued")
    if not isinstance(is_requeued_value, bool):
        raise ValidationError("Persisted orchestration context missing is_requeued flag.")
    execution_universal_ids = _coerce_execution_universal_ids(data.get("execution_uids"))
    parameter_overrides = _coerce_parameter_overrides(data.get("parameter_overrides"))
    parameter_snapshot = _coerce_parameter_snapshot(data.get("parameter_snapshot"))
    excluded_universal_ids = _coerce_excluded_universal_ids(data.get("excluded_uids"))
    dedup_hash = _coerce_optional_string(
        data.get("dedup_hash"),
        message="Persisted orchestration context dedup_hash must be a string or null.",
    )
    request_payload = _coerce_json_dict(
        data.get("request_payload"),
        message="Persisted orchestration context request_payload must be a JSON object.",
    )
    request_event_type = _coerce_required_string(
        data.get("request_event_type"),
        message="Persisted orchestration context missing request_event_type.",
    )
    request_context_data = _coerce_json_dict(
        data.get("request_context"),
        message="Persisted orchestration context request_context must be a JSON object.",
    )
    required_capabilities = _coerce_required_string_list(
        data.get("required_capabilities"),
        message="Persisted orchestration context missing required_capabilities.",
    )
    required_modalities = _coerce_required_string_list(
        data.get("required_modalities"),
        message="Persisted orchestration context missing required_modalities.",
    )
    request_source = _coerce_request_source(data.get("request_source"))
    delivery_mode = _coerce_required_string(
        data.get("delivery_mode"),
        message="Persisted orchestration context missing delivery_mode.",
    )
    startup_params = _coerce_json_dict(
        data.get("startup_params"),
        message="Persisted orchestration context startup_params must be a JSON object.",
    )
    inference_params = _coerce_json_dict(
        data.get("inference_params"),
        message="Persisted orchestration context inference_params must be a JSON object.",
    )
    parameter_version = _coerce_optional_int(
        data.get("parameter_version"),
        message="Persisted orchestration context parameter_version must be an int or null.",
    )
    startup_param_fingerprint = _coerce_optional_string(
        data.get("startup_param_fingerprint"),
        message="Persisted orchestration context startup_param_fingerprint must be a string or null.",
    )
    dedup_lead_task_id = _coerce_optional_string(
        data.get("dedup_lead_task_id"),
        message="Persisted orchestration context dedup_lead_task_id must be a string or null.",
    )
    return OrchestrationContextPersistedFields(
        execution_universal_ids=execution_universal_ids,
        parameter_overrides=parameter_overrides,
        parameter_snapshot=parameter_snapshot,
        virtual_model_name=_coerce_optional_string(data.get("virtual_model_name")),
        routing_key=_coerce_optional_string(data.get("routing_key")),
        plugin_name=_coerce_optional_string(data.get("plugin_name")),
        request_payload=request_payload,
        request_event_type=request_event_type,
        request_context_data=request_context_data,
        required_capabilities=required_capabilities,
        required_modalities=required_modalities,
        request_source=request_source,
        delivery_mode=delivery_mode,
        startup_params=startup_params,
        inference_params=inference_params,
        parameter_version=parameter_version,
        startup_param_fingerprint=startup_param_fingerprint,
        excluded_universal_ids=excluded_universal_ids,
        dedup_hash=dedup_hash,
        dedup_lead_task_id=dedup_lead_task_id,
        tracking_id=tracking_id,
        priority_assignment=RequestPriorityAssignment(
            priority=request_priority,
            queued_at=queued_at,
            priority_order=priority_order,
        ),
        is_requeued=is_requeued_value,
    )


def _coerce_execution_universal_ids(value: JSONValue) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValidationError("Persisted orchestration context missing execution_uids.")
    execution_universal_id_list: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ValidationError("Persisted orchestration context execution_uids must be strings.")
        execution_universal_id_list.append(item)
    execution_universal_ids = tuple(execution_universal_id_list)
    if len(set(execution_universal_ids)) != len(execution_universal_ids):
        raise ValidationError("Persisted orchestration context execution_uids must be unique.")
    return execution_universal_ids


def _coerce_parameter_overrides(value: JSONValue) -> dict[str, dict[str, JSONValue]]:
    parameter_overrides: dict[str, dict[str, JSONValue]] = {}
    if not isinstance(value, dict):
        raise ValidationError("Persisted orchestration context missing parameter_overrides.")
    for universal_id, override_value in value.items():
        if not isinstance(universal_id, str) or not is_json_dict(override_value):
            raise ValidationError(
                "Persisted orchestration context has invalid parameter_overrides.",
            )
        parameter_overrides[universal_id] = dict(override_value)
    return parameter_overrides


def _coerce_parameter_snapshot(value: JSONValue) -> tuple[dict[str, JSONValue], int] | None:
    if value is not None and not isinstance(value, list):
        raise ValidationError(
            "Persisted orchestration context parameter_snapshot must be a list or null.",
        )
    if value is None:
        return None
    if (
        len(value) != 2
        or not is_json_dict(value[0])
        or isinstance(value[1], bool)
        or not isinstance(value[1], int)
    ):
        raise ValidationError("Persisted orchestration context has invalid parameter_snapshot.")
    return (dict(value[0]), int(value[1]))


def _coerce_excluded_universal_ids(value: JSONValue) -> frozenset[str]:
    if not isinstance(value, list):
        raise ValidationError("Persisted orchestration context missing excluded_uids.")
    excluded_universal_id_list: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ValidationError("Persisted orchestration context excluded_uids must be strings.")
        excluded_universal_id_list.append(item)
    excluded_universal_ids = frozenset(excluded_universal_id_list)
    if len(excluded_universal_ids) != len(excluded_universal_id_list):
        raise ValidationError("Persisted orchestration context excluded_uids must be unique.")
    return excluded_universal_ids


def _coerce_request_source(value: JSONValue) -> RequestSource:
    if value is None:
        raise ValidationError("Persisted orchestration context missing request_source.")
    if not isinstance(value, str):
        raise ValidationError("request_source must be a string when persisted.")
    normalized = normalize_request_source(value)
    if normalized is None:
        raise ValidationError("Persisted orchestration context missing request_source.")
    return normalized


def _coerce_optional_int(value: JSONValue, *, message: str) -> int | None:
    if value is None:
        return None
    if not is_strict_int(value):
        raise ValidationError(message)
    return int(value)


def _coerce_optional_string(value: JSONValue, *, message: str | None = None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(
            message or "Persisted orchestration context value must be a string or null.",
        )
    return value


def _coerce_required_string(value: JSONValue, *, message: str) -> str:
    return require_non_empty_str(
        value,
        label="persisted_orchestration_context",
        build_error=ValidationError,
        invalid_message=message,
    )


def _coerce_required_string_list(value: JSONValue, *, message: str) -> tuple[str, ...]:
    if not is_str_list(value):
        raise ValidationError(message)
    return tuple(value)


def _coerce_json_dict(value: JSONValue, *, message: str) -> dict[str, JSONValue]:
    if not is_json_dict(value):
        raise ValidationError(message)
    return dict(value)
