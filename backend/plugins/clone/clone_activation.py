"""SoAI - Provisional clone runtime activation and logical commit [backend/plugins/clone/clone_activation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.database.clone_requests import (
    CLONE_PROVISIONAL_STATE,
    CloneCommitOutboxRecord,
    CloneCommitRequest,
)
from core.errors.exceptions import StateError
from core.events.authoritative_state_encoding import (
    encode_authoritative_plugin_state_event,
)
from core.events.domain_event_payload import build_domain_event_payload
from core.events.types_plugins import PluginRuntimeStateChangedEvent
from core.plugins.protocols_clone_database import DatabasePluginCloneTransactionsProtocol
from core.runtime.request_context import RequestContext
from core.serialization.json import serialize_json_compact_stable
from core.tasks.enums import TaskStatus
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from core.users.user_id import coerce_user_id
from plugins.clone.clone_plan import ClonePlan
from plugins.loader.loading_policy import PluginLoadOutcome, PluginLoadPolicy
from plugins.manager.instance_loading import load_plugin_activation
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol

__all__ = (
    "commit_clone_activation",
    "prepare_clone_activation",
    "record_clone_runtime_artifacts",
)


async def record_clone_runtime_artifacts(
    repository: DatabasePluginCloneTransactionsProtocol,
    task_id: str,
    target_plugin_name: str,
) -> tuple[int, ...]:
    artifact_ids: list[int] = []
    for artifact_type in ("database_record", "environment", "package_cache", "runtime"):
        artifact_ids.append(
            await repository.record_artifact(
                task_id,
                artifact_type,
                f"{artifact_type}://{task_id}",
                f"{artifact_type}://{target_plugin_name}",
            )
        )
    return tuple(artifact_ids)


async def prepare_clone_activation(
    plugin_manager: PluginManagerRuntimeProtocol,
    target_plugin_name: str,
) -> PluginLoadOutcome:
    return await load_plugin_activation(
        plugin_manager,
        target_plugin_name,
        policy=PluginLoadPolicy(
            catalog_state=CLONE_PROVISIONAL_STATE,
            announce=False,
            publish_failure_state=False,
        ),
        already_serialized=True,
    )


def _build_domain_event(
    *,
    event_id: str,
    event_type: str,
    timestamp: float,
    fields: JSONDict,
) -> CloneCommitOutboxRecord:
    payload = build_domain_event_payload(
        fields=fields,
        event_id=event_id,
        timestamp_unix=timestamp,
    )
    return CloneCommitOutboxRecord(
        event_id=event_id,
        event_type=event_type,
        payload_json=serialize_json_compact_stable(payload),
    )


async def commit_clone_activation(
    plugin_manager: PluginManagerRuntimeProtocol,
    *,
    plan: ClonePlan,
    task_id: str,
    fencing_token: int,
    display_name: str,
    outcome: PluginLoadOutcome,
    context: RequestContext | None,
) -> str:
    completed_at_ms = epoch_ms()
    timestamp = completed_at_ms / 1000.0
    state_event_id = f"plugin_clone_state:{plan.target_plugin_name}:1"
    state_event = PluginRuntimeStateChangedEvent(
        plugin_name=plan.target_plugin_name,
        previous_state=outcome.previous_state,
        new_state=outcome.initial_state,
        reason="Plugin clone activation committed.",
        context=context,
        event_id=state_event_id,
        timestamp=timestamp,
    )
    message = f"Plugin '{plan.source_display_name}' successfully cloned as '{display_name}'."
    if plan.clone_models and plan.target_models_path:
        message += " Models were included in the clone."
    loaded_event = _build_domain_event(
        event_id=f"plugin_clone_loaded:{plan.target_plugin_name}:{task_id}",
        event_type="PluginLoadedEvent",
        timestamp=timestamp,
        fields={
            "plugin_name": plan.target_plugin_name,
        },
    )
    config_event = _build_domain_event(
        event_id=f"plugin_clone_config:{plan.target_plugin_name}:{task_id}",
        event_type="TriggerConfigReconciliationCommand",
        timestamp=timestamp,
        fields={
            "reason": f"plugin_cloned:{plan.target_plugin_name}",
        },
    )
    task_complete_event = _build_domain_event(
        event_id=f"plugin_clone_task_complete:{task_id}",
        event_type="TaskCompleteEvent",
        timestamp=timestamp,
        fields={
            "success": True,
            "message": message,
            "task_id": task_id,
            "user_id": coerce_user_id(context.user_id if context is not None else None),
            "status": TaskStatus.COMPLETED.value,
            "error_code": None,
            "error_message": None,
        },
    )
    publication_sequence = (
        await plugin_manager.dependencies.databases.plugins.clone_transactions.commit(
            CloneCommitRequest(
                task_id=task_id,
                target_plugin_name=plan.target_plugin_name,
                fencing_token=fencing_token,
                ready_state=outcome.initial_state,
                completed_at_ms=completed_at_ms,
                task_result_json=serialize_json_compact_stable(
                    {
                        "target_plugin": plan.target_plugin_name,
                        "display_name": display_name,
                    }
                ),
                task_status_message=message,
                authoritative_event=CloneCommitOutboxRecord(
                    event_id=state_event_id,
                    event_type=type(state_event).__name__,
                    payload_json=encode_authoritative_plugin_state_event(state_event),
                ),
                domain_events=(loaded_event, config_event, task_complete_event),
            )
        )
    )
    if publication_sequence is None:
        raise StateError("Clone activation lost durable commit ownership.")
    state_event.publication_sequence = publication_sequence
    await plugin_manager.dependencies.infrastructure.state_aggregator.apply_authoritative_plugin_state_change(
        state_event
    )
    return message
