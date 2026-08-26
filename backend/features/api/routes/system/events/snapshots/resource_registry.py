"""SoAI - WebSocket snapshot resource registry [backend/features/api/routes/system/events/snapshots/resource_registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from fastapi import WebSocket

from features.api.routes.system.events.snapshots.handlers_chat_tool_calls import (
    snapshot_webui_chat_tool_call_live_events_page,
    snapshot_webui_chat_tool_calls_by_call_id,
)
from features.api.routes.system.events.snapshots.handlers_collections import (
    snapshot_models_collection,
    snapshot_plugins_capabilities_manifest,
    snapshot_plugins_collection,
    snapshot_prompts_collection,
    snapshot_system_metrics,
    snapshot_tasks_cancellations,
)
from features.api.routes.system.events.snapshots.handlers_files import (
    snapshot_file_explorer_list,
)
from features.api.routes.system.events.snapshots.handlers_hardware import (
    snapshot_hardware_capabilities,
    snapshot_hardware_gpu_capabilities,
    snapshot_hardware_gpu_settings_update,
    snapshot_hardware_gpu_slot_apply,
    snapshot_hardware_gpu_slot_preview,
    snapshot_hardware_gpu_slot_store,
    snapshot_hardware_gpu_slots,
    snapshot_hardware_gpu_soaibench_history,
    snapshot_hardware_gpu_soaibench_runs,
    snapshot_hardware_gpu_soaibench_start,
    snapshot_hardware_gpu_soaibench_status,
    snapshot_hardware_gpu_soaibench_stop,
    snapshot_hardware_process_kill,
    snapshot_hardware_processes,
    snapshot_hardware_snapshot,
)
from features.api.routes.system.events.snapshots.handlers_hardware_history import (
    snapshot_hardware_export,
    snapshot_hardware_history,
)
from features.api.routes.system.events.snapshots.handlers_latest_usage import (
    snapshot_models_last_used,
    snapshot_plugins_last_used,
)
from features.api.routes.system.events.snapshots.handlers_metrics import (
    snapshot_metrics_capabilities,
    snapshot_metrics_export,
    snapshot_metrics_history,
)
from features.api.routes.system.events.snapshots.handlers_models import (
    snapshot_model_parameters,
)
from features.api.routes.system.events.snapshots.handlers_openai_api_keys import (
    snapshot_openai_api_key_quota_status,
    snapshot_openai_api_key_usage,
)
from features.api.routes.system.events.snapshots.handlers_openai_models import (
    snapshot_openai_models,
)
from features.api.routes.system.events.snapshots.handlers_plugins import (
    snapshot_providers_collection,
)
from features.api.routes.system.events.snapshots.handlers_routing import (
    snapshot_routing_config,
    snapshot_routing_virtual_models,
)
from features.api.routes.system.events.snapshots.handlers_system import (
    snapshot_system_health,
    snapshot_system_info,
    snapshot_system_logs_core,
    snapshot_system_status,
)
from features.api.routes.system.events.snapshots.handlers_tasks import (
    snapshot_tasks_active,
    snapshot_tasks_by_id,
)
from features.api.routes.system.events.snapshots.handlers_wallpaper import (
    snapshot_wallpaper_status,
)
from features.api.routes.system.events.snapshots.handlers_webui import (
    snapshot_webui_chat_activity,
    snapshot_webui_chat_attention,
    snapshot_webui_notifications,
    snapshot_webui_permissions,
)
from features.api.routes.system.events.snapshots.handlers_webui_chat_agent import (
    snapshot_webui_chat_agent_checkpoint,
    snapshot_webui_chat_agent_plan,
    snapshot_webui_chat_agent_todo,
)
from features.api.streaming.websocket import WebsocketConnection

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

    type SnapshotHandler = Callable[
        [JSONDict, WebsocketConnection, WebSocket],
        Awaitable[JSONValue],
    ]

__all__ = ("resolve_snapshot_handler",)

SNAPSHOT_HANDLER_RULES: tuple[tuple[str, SnapshotHandler], ...] = (
    ("prompts.collection", snapshot_prompts_collection),
    ("models.collection", snapshot_models_collection),
    ("models.last_used", snapshot_models_last_used),
    ("models.parameters", snapshot_model_parameters),
    ("routing.config", snapshot_routing_config),
    ("routing.virtualModels", snapshot_routing_virtual_models),
    ("plugins.collection", snapshot_plugins_collection),
    ("plugins.last_used", snapshot_plugins_last_used),
    ("plugins.capabilities.manifest", snapshot_plugins_capabilities_manifest),
    ("providers.collection", snapshot_providers_collection),
    ("hardware.snapshot", snapshot_hardware_snapshot),
    ("hardware.capabilities", snapshot_hardware_capabilities),
    ("hardware.gpu.capabilities", snapshot_hardware_gpu_capabilities),
    ("hardware.gpu.soaibench.start", snapshot_hardware_gpu_soaibench_start),
    ("hardware.gpu.soaibench.status", snapshot_hardware_gpu_soaibench_status),
    ("hardware.gpu.soaibench.stop", snapshot_hardware_gpu_soaibench_stop),
    ("hardware.gpu.soaibench.history", snapshot_hardware_gpu_soaibench_history),
    ("hardware.gpu.soaibench.runs", snapshot_hardware_gpu_soaibench_runs),
    ("hardware.gpu.settings.update", snapshot_hardware_gpu_settings_update),
    ("hardware.gpu.slots", snapshot_hardware_gpu_slots),
    ("hardware.gpu.slots.preview", snapshot_hardware_gpu_slot_preview),
    ("hardware.gpu.slots.apply", snapshot_hardware_gpu_slot_apply),
    ("hardware.gpu.slots.store", snapshot_hardware_gpu_slot_store),
    ("hardware.processes", snapshot_hardware_processes),
    ("hardware.process.kill", snapshot_hardware_process_kill),
    ("tasks.active", snapshot_tasks_active),
    ("tasks.by_id", snapshot_tasks_by_id),
    ("tasks.cancellations", snapshot_tasks_cancellations),
    ("hardware.history", snapshot_hardware_history),
    ("hardware.export", snapshot_hardware_export),
    ("system.info", snapshot_system_info),
    ("system.health", snapshot_system_health),
    ("system.status", snapshot_system_status),
    ("system.logs.core", snapshot_system_logs_core),
    ("system.metrics", snapshot_system_metrics),
    ("system.metrics.capabilities", snapshot_metrics_capabilities),
    ("system.metrics.history", snapshot_metrics_history),
    ("system.metrics.export", snapshot_metrics_export),
    ("file_explorer.list", snapshot_file_explorer_list),
    ("openai_api_keys.quota.status", snapshot_openai_api_key_quota_status),
    ("openai_api_keys.usage", snapshot_openai_api_key_usage),
    ("openai.models", snapshot_openai_models),
    ("webui.wallpaper.status", snapshot_wallpaper_status),
    ("webui.permissions", snapshot_webui_permissions),
    ("webui.notifications", snapshot_webui_notifications),
    ("webui.chat.attention", snapshot_webui_chat_attention),
    ("webui.chat.activity", snapshot_webui_chat_activity),
    ("webui.chat.tool_calls.by_call_id", snapshot_webui_chat_tool_calls_by_call_id),
    ("webui.chat.tool_call_live_events.page", snapshot_webui_chat_tool_call_live_events_page),
    ("webui.chat.agent.checkpoint", snapshot_webui_chat_agent_checkpoint),
    ("webui.chat.agent.todo", snapshot_webui_chat_agent_todo),
    ("webui.chat.agent.plan", snapshot_webui_chat_agent_plan),
)


def resolve_snapshot_handler(resource: str) -> SnapshotHandler | None:
    for allowed_resource, handler in SNAPSHOT_HANDLER_RULES:
        if resource == allowed_resource:
            return handler
    return None
