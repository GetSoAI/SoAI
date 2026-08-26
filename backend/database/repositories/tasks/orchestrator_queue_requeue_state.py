"""SoAI - Durable requeue state extraction [backend/database/repositories/tasks/orchestrator_queue_requeue_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from functools import partial
from typing import NoReturn

from core.errors.exceptions import StateError, ValidationError
from core.orchestrator.request_priority import RequestPriority
from core.runtime.request_sources import normalize_request_source
from core.serialization.json_parsing import parse_json_value
from core.validation.record_fields import (
    require_non_empty_str,
    require_number,
    require_optional_non_empty_str,
)
from database.core.query_execution import sync_fetch_one_as_dict

__all__ = ("OrchestratorQueueRequeueState", "resolve_orchestrator_queue_requeue_state")

OPERATION = "database.tasks.requeue_orchestrated_inference_task"


@dataclass(frozen=True, slots=True)
class OrchestratorQueueRequeueState:
    routing_key: str
    plugin_name: str | None
    dedup_hash: str | None
    dedup_lead_task_id: str | None
    request_source: str
    delivery_mode: str
    request_priority: RequestPriority
    priority_order_at_ms: int


def _raise_invalid_state(task_id: str, message: str) -> NoReturn:
    raise StateError(message, operation=OPERATION, details={"task_id": task_id})


def _build_invalid_state_error(task_id: str, message: str) -> StateError:
    return StateError(message, operation=OPERATION, details={"task_id": task_id})


def resolve_orchestrator_queue_requeue_state(
    conn: sqlite3.Connection,
    task_id: str,
) -> OrchestratorQueueRequeueState:
    row = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT orchestration_state FROM unified_tasks WHERE task_id = ?",
            (task_id,),
        ),
    )
    raw_state = row.get("orchestration_state") if row else None
    if not isinstance(raw_state, str) or not raw_state:
        _raise_invalid_state(
            task_id,
            "Cannot requeue orchestrated task without persisted orchestration state.",
        )
    try:
        parsed = parse_json_value(raw_state)
    except ValidationError as exception:
        raise StateError(
            "Cannot requeue orchestrated task with invalid persisted orchestration state.",
            operation=OPERATION,
            details={"task_id": task_id},
        ) from exception
    if not isinstance(parsed, dict):
        _raise_invalid_state(
            task_id,
            "Cannot requeue orchestrated task with non-object persisted orchestration state.",
        )
    build_error = partial(_build_invalid_state_error, task_id)
    routing_key = require_non_empty_str(
        parsed.get("routing_key"),
        label="routing key",
        build_error=build_error,
        invalid_message="Cannot requeue orchestrated task without a routing key.",
    )
    plugin_name = require_optional_non_empty_str(
        parsed.get("plugin_name"),
        label="plugin name",
        build_error=build_error,
        invalid_message="Cannot requeue orchestrated task with an invalid plugin name.",
    )
    dedup_hash = require_optional_non_empty_str(
        parsed.get("dedup_hash"),
        label="dedup hash",
        build_error=build_error,
        invalid_message="Cannot requeue orchestrated task with an invalid dedup hash.",
    )
    dedup_lead_task_id = require_optional_non_empty_str(
        parsed.get("dedup_lead_task_id"),
        label="dedup lead task id",
        build_error=build_error,
        invalid_message="Cannot requeue orchestrated task with an invalid dedup lead task id.",
    )
    request_source_value = parsed.get("request_source")
    if not isinstance(request_source_value, str):
        _raise_invalid_state(task_id, "Cannot requeue orchestrated task without a request source.")
    try:
        request_source = normalize_request_source(request_source_value)
    except ValidationError as exception:
        raise StateError(
            "Cannot requeue orchestrated task with an invalid request source.",
            operation=OPERATION,
            details={"task_id": task_id},
        ) from exception
    if request_source is None:
        _raise_invalid_state(
            task_id,
            "Cannot requeue orchestrated task with an invalid request source.",
        )
    delivery_mode = require_non_empty_str(
        parsed.get("delivery_mode"),
        label="delivery mode",
        build_error=build_error,
        invalid_message="Cannot requeue orchestrated task without a delivery mode.",
    )
    request_priority_value = parsed.get("request_priority")
    if not isinstance(request_priority_value, str):
        _raise_invalid_state(
            task_id, "Cannot requeue orchestrated task with invalid request priority."
        )
    try:
        request_priority = RequestPriority(request_priority_value)
    except ValueError as exception:
        raise StateError(
            "Cannot requeue orchestrated task with invalid request priority.",
            operation=OPERATION,
            details={"task_id": task_id},
        ) from exception
    priority_order_value = require_number(
        parsed.get("priority_order"),
        label="priority order",
        build_error=build_error,
        invalid_message="Cannot requeue orchestrated task without a priority order.",
        finite_message="Cannot requeue orchestrated task with invalid priority order.",
    )
    if priority_order_value < 0:
        _raise_invalid_state(
            task_id, "Cannot requeue orchestrated task with invalid priority order."
        )
    return OrchestratorQueueRequeueState(
        routing_key=routing_key,
        plugin_name=plugin_name,
        dedup_hash=dedup_hash,
        dedup_lead_task_id=dedup_lead_task_id,
        request_source=request_source,
        delivery_mode=delivery_mode,
        request_priority=request_priority,
        priority_order_at_ms=int(float(priority_order_value) * 1000.0),
    )
