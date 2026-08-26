"""SoAI - Plugin lifecycle task initialization [backend/plugins/lifecycle_task_initialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.context import create_system_cancellation_id
from core.mutations.identifiers import build_mutation_claim_cancellation_id
from core.runtime.ownership import resolve_http_owner_id
from core.tasks.errors import TaskIDCollisionError
from core.tasks.type_catalog import TASK_TYPE_BACKGROUND_JOB
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from core.runtime.request_context import RequestContext
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONDict
    from plugins.lifecycle_dependencies import PluginLifecycleDependencies

__all__ = ("LifecycleTaskInitialization", "initialize_lifecycle_task")


@dataclass(frozen=True, slots=True)
class LifecycleTaskInitialization:
    task_id: str
    cancellation_id: str


async def initialize_lifecycle_task(
    deps: PluginLifecycleDependencies,
    registry: TaskRegistryProtocol,
    *,
    task_type: str,
    plugin_name: str | None,
    metadata: JSONDict | None,
    user_id: int,
    task_id: str | None,
    context: RequestContext | None,
) -> LifecycleTaskInitialization:
    resolved_task_id = (task_id or "").strip()
    if not resolved_task_id and context is not None:
        candidate = context.task_id
        if isinstance(candidate, str):
            resolved_task_id = candidate.strip()
    owner_type_value, owner_id_value = _resolve_lifecycle_owner(context, user_id)
    expected_task_type = deps.plugin_task_type_map.get(task_type, TASK_TYPE_BACKGROUND_JOB)
    existing = await registry.get(resolved_task_id) if resolved_task_id else None
    mutation_fencing_token = context.mutation_fencing_token if context is not None else None
    if mutation_fencing_token is not None:
        if existing is None or not await registry.database_tasks.validate_mutation_claim(
            resolved_task_id,
            mutation_fencing_token,
            now_ms=epoch_ms(),
        ):
            raise TaskIDCollisionError(
                resolved_task_id or "missing-mutation-task",
                existing.status.value if existing is not None else "missing",
            )
    if existing is not None:
        if existing.status.is_terminal():
            raise TaskIDCollisionError(existing.task_id, existing.status.value)
        if (
            existing.owner_id != owner_id_value
            or existing.owner_type != owner_type_value
            or existing.task_type != expected_task_type
        ):
            raise TaskIDCollisionError(existing.task_id, existing.status.value)
        cancellation_id = existing.cancellation_id
        if mutation_fencing_token is not None:
            cancellation_id = build_mutation_claim_cancellation_id(
                existing.cancellation_id,
                existing.task_id,
                mutation_fencing_token,
            )
        resolved = LifecycleTaskInitialization(
            task_id=existing.task_id,
            cancellation_id=cancellation_id,
        )
    else:
        full_metadata = _build_lifecycle_metadata(
            task_type=task_type,
            plugin_name=plugin_name,
            metadata=metadata,
            context=context,
        )
        created = await deps.task_create(
            registry,
            task_type=expected_task_type,
            user_id=user_id,
            owner_id=owner_id_value,
            owner_type=owner_type_value,
            task_id=resolved_task_id or None,
            cancellation_id=_resolve_cancellation_id(task_type, context),
            ttl_ms=deps.plugin_task_ttl_ms,
            progress_total=100,
            metadata=full_metadata,
        )
        resolved = LifecycleTaskInitialization(
            task_id=created.task_id,
            cancellation_id=created.cancellation_id,
        )
    if context is not None:
        context.task_id = resolved.task_id
    cancellation_id = resolved.cancellation_id or create_system_cancellation_id(
        f"plugin_lifecycle:{task_type}",
    )
    return LifecycleTaskInitialization(task_id=resolved.task_id, cancellation_id=cancellation_id)


def _resolve_lifecycle_owner(context: RequestContext | None, user_id: int) -> tuple[str, str]:
    if context is not None:
        return ("http_request", resolve_http_owner_id(context))
    if user_id:
        return ("http_request", f"http_user:{int(user_id)}")
    return ("system", "system")


def _build_lifecycle_metadata(
    *,
    task_type: str,
    plugin_name: str | None,
    metadata: JSONDict | None,
    context: RequestContext | None,
) -> JSONDict:
    full_metadata: JSONDict = {"task_type_key": task_type}
    if context is not None:
        full_metadata["trace_id"] = context.trace_id
    if plugin_name is not None:
        full_metadata["plugin_name"] = plugin_name
    if metadata:
        full_metadata.update(metadata)
    return full_metadata


def _resolve_cancellation_id(task_type: str, context: RequestContext | None) -> str:
    if context is not None and context.cancellation_id:
        return str(context.cancellation_id)
    return create_system_cancellation_id(f"plugin_lifecycle:{task_type}")
