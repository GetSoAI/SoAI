"""SoAI - Task serialization protocol surfaces [backend/core/tasks/protocols_serialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from core.orchestrator.request_priority import RequestPriorityAssignment
from core.tasks.enums import TaskStatus
from core.tasks.type_catalog import TaskTypeId
from core.types.dict import FrozenJsonDict
from core.types.json import JSONValue

__all__ = (
    "OrchestrationContextPersistenceViewProtocol",
    "OrchestrationContextSerializationSurfaceProtocol",
    "TaskSerializationSurfaceProtocol",
)


class OrchestrationContextSerializationSurfaceProtocol(Protocol):
    @property
    def tracking_id(self) -> str: ...

    @property
    def excluded_universal_ids(self) -> frozenset[str]: ...

    @property
    def virtual_model_name(self) -> str | None: ...


class OrchestrationContextPersistenceViewProtocol(Protocol):
    @property
    def parameter_snapshot(self) -> tuple[dict[str, JSONValue], int] | None: ...

    @property
    def execution_universal_ids(self) -> tuple[str, ...]: ...

    @property
    def parameter_overrides(self) -> dict[str, dict[str, JSONValue]]: ...

    @property
    def virtual_model_name(self) -> str | None: ...

    @property
    def routing_key(self) -> str | None: ...

    @property
    def plugin_name(self) -> str | None: ...

    @property
    def request_payload(self) -> dict[str, JSONValue]: ...

    @property
    def request_event_type(self) -> str: ...

    @property
    def request_context_data(self) -> dict[str, JSONValue]: ...

    @property
    def required_capabilities(self) -> tuple[str, ...]: ...

    @property
    def required_modalities(self) -> tuple[str, ...]: ...

    @property
    def request_source(self) -> str | None: ...

    @property
    def delivery_mode(self) -> str | None: ...

    @property
    def startup_params(self) -> dict[str, JSONValue]: ...

    @property
    def inference_params(self) -> dict[str, JSONValue]: ...

    @property
    def parameter_version(self) -> int | None: ...

    @property
    def startup_param_fingerprint(self) -> str | None: ...

    @property
    def excluded_universal_ids(self) -> frozenset[str]: ...

    @property
    def dedup_hash(self) -> str | None: ...

    @property
    def dedup_lead_task_id(self) -> str | None: ...

    @property
    def tracking_id(self) -> str: ...

    @property
    def queued_at(self) -> float: ...

    @property
    def priority_assignment(self) -> RequestPriorityAssignment: ...

    @property
    def is_requeued(self) -> bool: ...


class TaskSerializationSurfaceProtocol(Protocol):
    task_id: str
    task_type: TaskTypeId
    status: TaskStatus
    user_id: int
    owner_type: str
    owner_id: str
    cancellation_id: str
    created_at_ms: int
    updated_at_ms: int
    completed_at_ms: int | None
    ttl_ms: int | None
    poll_interval_ms: int
    progress_current: int | None
    progress_total: int | None
    status_message: str | None
    cancellation_requested_at_ms: int | None
    metadata: FrozenJsonDict
    result: dict[str, JSONValue] | None
    error_code: int | None
    error_type: str | None
    error_message: str | None

    @property
    def orchestration_context(self) -> OrchestrationContextSerializationSurfaceProtocol | None: ...

    @property
    def snapshot_tracking_id(self) -> str | None: ...

    @property
    def snapshot_excluded_universal_ids(self) -> frozenset[str] | None: ...

    @property
    def snapshot_virtual_model_name(self) -> str | None: ...

    @property
    def ttl_expires_at_ms(self) -> int | None: ...

    def progress_percent(self) -> float | None: ...
