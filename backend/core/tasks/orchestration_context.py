"""SoAI - Orchestration context dataclass for inference request tracking [backend/core/tasks/orchestration_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import dataclasses
import hashlib
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.orchestrator.request_priority import (
    RequestPriorityAssignment,
    build_default_priority_assignment,
)
from core.runtime.request_sources import RequestSource
from core.serialization.json import serialize_json_compact_stable
from core.tasks.orchestration_context_persistence import (
    deserialize_orchestration_context,
    serialize_orchestration_context,
)
from core.types.json import JSONValue

if TYPE_CHECKING:
    from core.events.types_models_requests import InferenceRequestReceived
    from core.types.json import JSONDict

__all__ = (
    "OrchestrationContext",
    "build_startup_param_fingerprint",
    "with_parameter_snapshot_state",
)


@dataclass(frozen=True, slots=True)
class OrchestrationContext:
    priority_assignment: RequestPriorityAssignment = field(
        default_factory=build_default_priority_assignment,
    )
    event: InferenceRequestReceived | None = field(
        default=None,
        repr=False,
        compare=False,
        hash=False,
    )
    execution_universal_ids: tuple[str, ...] = field(default_factory=tuple)
    parameter_overrides: dict[str, dict[str, JSONValue]] = field(
        default_factory=dict[str, dict[str, JSONValue]],
        hash=False,
    )
    parameter_snapshot: tuple[dict[str, JSONValue], int] | None = field(default=None, hash=False)
    virtual_model_name: str | None = None
    routing_key: str | None = None
    plugin_name: str | None = None
    request_payload: dict[str, JSONValue] = field(default_factory=dict[str, JSONValue], hash=False)
    request_event_type: str = "InferenceRequestReceived"
    request_context_data: dict[str, JSONValue] = field(
        default_factory=dict[str, JSONValue],
        hash=False,
    )
    required_capabilities: tuple[str, ...] = field(default_factory=tuple)
    required_modalities: tuple[str, ...] = field(default_factory=tuple)
    request_source: RequestSource | None = None
    delivery_mode: str | None = None
    startup_params: dict[str, JSONValue] = field(default_factory=dict[str, JSONValue], hash=False)
    inference_params: dict[str, JSONValue] = field(default_factory=dict[str, JSONValue], hash=False)
    parameter_version: int | None = None
    startup_param_fingerprint: str | None = None
    excluded_universal_ids: frozenset[str] = field(default_factory=frozenset[str])
    dedup_hash: str | None = None
    dedup_lead_task_id: str | None = None
    tracking_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    is_requeued: bool = False
    delivery_in_progress: bool = False
    delivery_version: int = 0
    streaming_started: bool = False
    prompt_slot_active: bool = False
    prompt_slot_generation: int | None = None

    @property
    def queued_at(self) -> float:
        return self.priority_assignment.queued_at

    def with_reset_delivery_state(self) -> OrchestrationContext:
        return dataclasses.replace(
            self,
            delivery_in_progress=False,
            streaming_started=False,
        )

    def to_persistable_dict(self) -> JSONDict:
        return serialize_orchestration_context(self)

    @classmethod
    def from_persisted_dict(cls, data: JSONDict) -> OrchestrationContext:
        fields = deserialize_orchestration_context(data)
        return cls(
            priority_assignment=fields.priority_assignment,
            execution_universal_ids=fields.execution_universal_ids,
            parameter_overrides=fields.parameter_overrides,
            parameter_snapshot=fields.parameter_snapshot,
            virtual_model_name=fields.virtual_model_name,
            routing_key=fields.routing_key,
            plugin_name=fields.plugin_name,
            request_payload=fields.request_payload,
            request_event_type=fields.request_event_type,
            request_context_data=fields.request_context_data,
            required_capabilities=fields.required_capabilities,
            required_modalities=fields.required_modalities,
            request_source=fields.request_source,
            delivery_mode=fields.delivery_mode,
            startup_params=fields.startup_params,
            inference_params=fields.inference_params,
            parameter_version=fields.parameter_version,
            startup_param_fingerprint=fields.startup_param_fingerprint,
            excluded_universal_ids=fields.excluded_universal_ids,
            dedup_hash=fields.dedup_hash,
            dedup_lead_task_id=fields.dedup_lead_task_id,
            tracking_id=fields.tracking_id,
            is_requeued=fields.is_requeued,
        )


def with_parameter_snapshot_state(
    context: OrchestrationContext,
    *,
    parameter_snapshot: tuple[dict[str, JSONValue], int] | None,
    startup_params: dict[str, JSONValue],
    inference_params: dict[str, JSONValue],
    parameter_version: int | None,
    startup_param_fingerprint: str | None,
) -> OrchestrationContext:
    return dataclasses.replace(
        context,
        parameter_snapshot=parameter_snapshot,
        startup_params=startup_params,
        inference_params=inference_params,
        parameter_version=parameter_version,
        startup_param_fingerprint=startup_param_fingerprint,
    )


def build_startup_param_fingerprint(parameters: dict[str, JSONValue]) -> str:
    normalized = parameters or {}
    return hashlib.sha256(serialize_json_compact_stable(normalized).encode("utf-8")).hexdigest()
