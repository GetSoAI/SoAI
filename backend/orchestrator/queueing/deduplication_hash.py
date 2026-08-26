"""SoAI - Request deduplication hash calculation [backend/orchestrator/queueing/deduplication_hash.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib

from core.errors.exceptions import StateError
from core.orchestrator.routing_config import RoutingConfig
from core.serialization.json import (
    serialize_json_compact_stable,
    serialize_json_compact_stable_safe_default,
)
from core.tasks.orchestration_context import OrchestrationContext

__all__ = ("calculate_dedup_hash",)


def calculate_dedup_hash(
    context: OrchestrationContext,
    *,
    routing_config: RoutingConfig,
) -> str:
    event = context.event
    if event is None:
        raise StateError("Missing inference event for task dedup hash")
    hasher = hashlib.sha256()
    hasher.update(context.priority_assignment.priority.value.encode("utf-8"))
    hasher.update(
        serialize_json_compact_stable_safe_default(
            list(context.execution_universal_ids),
        ).encode("utf-8"),
    )
    if context.parameter_snapshot:
        hasher.update(serialize_json_compact_stable(context.parameter_snapshot).encode("utf-8"))
    payload = event.payload
    deduplication_keys = (
        tuple(routing_config.deduplication_keys) if routing_config.deduplication_keys else ()
    )
    if any(key == "payload_hash" for key in deduplication_keys) or (not deduplication_keys):
        payload_items = sorted(
            (payload_key, payload_value)
            for payload_key, payload_value in payload.items()
            if payload_key != "stream"
        )
    else:
        payload_items = [
            (key, payload[key])
            for key in sorted({key.strip() for key in deduplication_keys if key.strip()})
            if key != "stream" and key in payload
        ]
    hasher.update(serialize_json_compact_stable(payload_items).encode("utf-8"))
    return hasher.hexdigest()
