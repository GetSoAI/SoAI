"""SoAI - Orchestration context persistence serialization and parsing [backend/core/tasks/orchestration_context_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tasks.orchestration_context_persisted_fields import (
    OrchestrationContextPersistedFields,
    deserialize_orchestration_context,
)
from core.tasks.protocols_serialization import (
    OrchestrationContextPersistenceViewProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "OrchestrationContextPersistedFields",
    "deserialize_orchestration_context",
    "serialize_orchestration_context",
)


def serialize_orchestration_context(
    context: OrchestrationContextPersistenceViewProtocol,
) -> JSONDict:
    parameter_snapshot: JSONValue | None = None
    if context.parameter_snapshot is not None:
        params, version = context.parameter_snapshot
        parameter_snapshot = [params, version]
    return {
        "execution_uids": list(context.execution_universal_ids),
        "parameter_overrides": context.parameter_overrides,
        "parameter_snapshot": parameter_snapshot,
        "virtual_model_name": context.virtual_model_name,
        "routing_key": context.routing_key,
        "plugin_name": context.plugin_name,
        "request_payload": context.request_payload,
        "request_event_type": context.request_event_type,
        "request_context": context.request_context_data,
        "required_capabilities": list(context.required_capabilities),
        "required_modalities": list(context.required_modalities),
        "request_source": context.request_source,
        "delivery_mode": context.delivery_mode,
        "startup_params": context.startup_params,
        "inference_params": context.inference_params,
        "parameter_version": context.parameter_version,
        "startup_param_fingerprint": context.startup_param_fingerprint,
        "excluded_uids": list(context.excluded_universal_ids),
        "dedup_hash": context.dedup_hash,
        "dedup_lead_task_id": context.dedup_lead_task_id,
        "tracking_id": context.tracking_id,
        "queued_at": context.queued_at,
        "request_priority": context.priority_assignment.priority.value,
        "priority_order": context.priority_assignment.priority_order,
        "is_requeued": context.is_requeued,
    }
