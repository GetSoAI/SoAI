"""SoAI - System event visibility and access permissions [backend/features/api/routes/system/events/permissions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.events.types_base import Event
from core.events.types_conversation_durable import (
    ConversationAttentionChangedEvent,
    ConversationInputTerminalEvent,
)
from core.events.types_file_explorer import FileSystemChangedEvent
from core.events.types_mcp import KnowledgePromptStateChangedEvent, MCPNotificationEvent
from core.events.types_system import (
    ChatStreamActivityChangedEvent,
    ChatStreamEvent,
    ChatStreamStatusPreviewEvent,
    ConversationAttachmentChangedEvent,
    ConversationCreatedEvent,
    ConversationDeletedEvent,
    ConversationDraftChangedEvent,
    ConversationInputsChangedEvent,
    ConversationUpdatedEvent,
    KnowledgeAttachmentChangedEvent,
    MessageSavedEvent,
    ModelTestStreamEvent,
    SoAIBenchRunUpdatedEvent,
    ThinkingTailCompletedEvent,
    ToolCallCompletedEvent,
    ToolCallCreatedEvent,
    ToolCallLiveUpdatedEvent,
    ToolCallOutputDeltaEvent,
    ToolCallStartedEvent,
)
from core.events.types_tasks import (
    TaskCompleteEvent,
    TaskCreatedEvent,
    TaskProgressEvent,
    TaskStatusChangedEvent,
)
from core.events.types_webui import (
    AutomationCreatedEvent,
    AutomationDeletedEvent,
    AutomationRunCreatedEvent,
    AutomationRunUpdatedEvent,
    AutomationUpdatedEvent,
    NotificationCreatedEvent,
    NotificationDeletedEvent,
    NotificationsClearedEvent,
    NotificationsMarkedReadEvent,
    PromptListUpdatedEvent,
    UserPasswordChangedEvent,
    UserSessionInvalidatedEvent,
    UserUsernameChangedEvent,
)
from core.mcp.protocols_main import MCPServerProtocol
from core.state.access import AccessAction
from core.users.user_id import coerce_optional_user_id
from features.api.routes.system.events.agent_event_types import (
    is_user_scoped_agent_event,
)
from features.api.routes.system.events.file_event_visibility import (
    file_system_event_visible_to_user,
)

if TYPE_CHECKING:
    from core.files.protocols import FilesPathResolverProtocol
    from core.types.json import JSONValue

__all__ = ("event_visible_to_user", "resolve_current_user_id")

SNAPSHOT_PERMISSION_RULES: tuple[tuple[str, AccessAction], ...] = (
    ("models.collection", AccessAction.MODEL_READ),
    ("models.last_used", AccessAction.MODEL_READ),
    ("plugins.collection", AccessAction.PLUGIN_READ),
    ("plugins.last_used", AccessAction.PLUGIN_READ),
    ("plugins.capabilities.manifest", AccessAction.PLUGIN_READ),
    ("prompts.collection", AccessAction.AUTH_COOKIE),
    ("models.parameters", AccessAction.MODEL_READ),
    ("routing.config", AccessAction.MODEL_ROUTING_READ),
    ("routing.virtualModels", AccessAction.MODEL_ROUTING_READ),
    ("system.metrics", AccessAction.AUTH_COOKIE),
    ("system.metrics.capabilities", AccessAction.AUTH_COOKIE),
    ("system.metrics.history", AccessAction.AUTH_COOKIE),
    ("system.metrics.export", AccessAction.AUTH_COOKIE),
    ("providers.collection", AccessAction.PLUGIN_READ),
    ("hardware.snapshot", AccessAction.HARDWARE_READ),
    ("hardware.capabilities", AccessAction.HARDWARE_READ),
    ("hardware.gpu.capabilities", AccessAction.HARDWARE_READ),
    ("hardware.gpu.soaibench.start", AccessAction.HW_GPU_TUNING),
    ("hardware.gpu.soaibench.status", AccessAction.HARDWARE_READ),
    ("hardware.gpu.soaibench.stop", AccessAction.RECOVERY_ADMIN),
    ("hardware.gpu.soaibench.history", AccessAction.HARDWARE_READ),
    ("hardware.gpu.soaibench.runs", AccessAction.HARDWARE_READ),
    ("hardware.gpu.settings.update", AccessAction.HW_GPU_TUNING),
    ("hardware.gpu.slots", AccessAction.HARDWARE_READ),
    ("hardware.gpu.slots.preview", AccessAction.HW_GPU_TUNING),
    ("hardware.gpu.slots.apply", AccessAction.HW_GPU_TUNING),
    ("hardware.gpu.slots.store", AccessAction.HW_GPU_TUNING),
    ("hardware.processes", AccessAction.HW_PROCESS_VIEW),
    ("hardware.process.kill", AccessAction.RECOVERY_ADMIN),
    ("tasks.active", AccessAction.AUTH_COOKIE),
    ("tasks.by_id", AccessAction.AUTH_COOKIE),
    ("tasks.cancellations", AccessAction.REQUEST_CANCELLATION_ADMIN),
    ("hardware.history", AccessAction.HARDWARE_READ),
    ("hardware.export", AccessAction.HARDWARE_READ),
    ("system.info", AccessAction.SYSTEM_STATUS_READ),
    ("system.health", AccessAction.SYSTEM_STATUS_READ),
    ("system.status", AccessAction.SYSTEM_STATUS_READ),
    ("system.power.operations", AccessAction.SYSTEM_POWER),
    ("system.logs.core", AccessAction.LOG_ACCESS),
    ("webui.wallpaper.status", AccessAction.AUTH_COOKIE),
    ("webui.permissions", AccessAction.AUTH_COOKIE),
    ("webui.notifications", AccessAction.NOTIFICATIONS),
    ("webui.chat.attention", AccessAction.AUTH_COOKIE),
    ("webui.chat.activity", AccessAction.AUTH_COOKIE),
    ("webui.chat.tool_calls.by_call_id", AccessAction.AUTH_COOKIE),
    ("webui.chat.tool_call_live_events.page", AccessAction.AUTH_COOKIE),
    ("webui.chat.agent.checkpoint", AccessAction.AUTH_COOKIE),
    ("webui.chat.agent.todo", AccessAction.AUTH_COOKIE),
    ("webui.chat.agent.plan", AccessAction.AUTH_COOKIE),
    ("file_explorer.list", AccessAction.FILE_EXPLORER_READ),
    ("openai_api_keys.quota.status", AccessAction.OPENAI_API_ADMIN),
    ("openai_api_keys.usage", AccessAction.OPENAI_API_ADMIN),
    ("openai.models", AccessAction.OPENAI_API),
)


def resolve_current_user_id(current_user: Mapping[str, JSONValue]) -> int:
    candidate_user_id = current_user.get("id")
    if isinstance(candidate_user_id, Sequence) and not isinstance(candidate_user_id, str | bytes):
        candidate_user_id = None
    if isinstance(candidate_user_id, bytes):
        candidate_user_id = None
    return coerce_optional_user_id(candidate_user_id) or 0


def event_visible_to_user(
    event: Event,
    *,
    current_user: Mapping[str, JSONValue],
    files: FilesPathResolverProtocol,
    mcp_server: MCPServerProtocol | None,
) -> bool:
    user_id = resolve_current_user_id(current_user)
    if isinstance(event, PromptListUpdatedEvent):
        return event.user_id == user_id
    if isinstance(event, ConversationAttentionChangedEvent):
        return event.user_id == user_id
    if isinstance(
        event,
        UserPasswordChangedEvent | UserUsernameChangedEvent | UserSessionInvalidatedEvent,
    ):
        return event.user_id == user_id
    if isinstance(
        event,
        NotificationCreatedEvent
        | NotificationDeletedEvent
        | NotificationsClearedEvent
        | NotificationsMarkedReadEvent,
    ):
        return event.user_id == user_id
    if isinstance(
        event,
        AutomationCreatedEvent
        | AutomationUpdatedEvent
        | AutomationDeletedEvent
        | AutomationRunCreatedEvent
        | AutomationRunUpdatedEvent,
    ):
        return event.user_id == user_id
    if isinstance(
        event,
        ConversationCreatedEvent
        | ConversationUpdatedEvent
        | ConversationDeletedEvent
        | ConversationDraftChangedEvent
        | ConversationAttachmentChangedEvent
        | KnowledgeAttachmentChangedEvent
        | MessageSavedEvent
        | ConversationInputsChangedEvent
        | ConversationInputTerminalEvent,
    ):
        return event.user_id == user_id
    if isinstance(
        event,
        ToolCallCreatedEvent
        | ToolCallStartedEvent
        | ToolCallCompletedEvent
        | ToolCallLiveUpdatedEvent
        | ToolCallOutputDeltaEvent
        | ThinkingTailCompletedEvent,
    ):
        return event.user_id == user_id
    if isinstance(event, ChatStreamEvent | ChatStreamActivityChangedEvent):
        return event.user_id == user_id
    if isinstance(event, ChatStreamStatusPreviewEvent):
        return event.user_id == user_id
    if isinstance(event, KnowledgePromptStateChangedEvent):
        return event.user_id == user_id
    if isinstance(event, ModelTestStreamEvent):
        return event.user_id == user_id
    if isinstance(event, SoAIBenchRunUpdatedEvent):
        return event.user_id == user_id
    if isinstance(event, FileSystemChangedEvent):
        return file_system_event_visible_to_user(
            event,
            current_user=current_user,
            files=files,
        )
    if is_user_scoped_agent_event(event):
        return event.user_id == user_id
    if isinstance(
        event,
        TaskCreatedEvent | TaskStatusChangedEvent | TaskProgressEvent | TaskCompleteEvent,
    ):
        try:
            event_user_id = event.user_id
        except AttributeError:
            event_user_id = None
        if event_user_id is None:
            return False
        normalized_event_user = coerce_optional_user_id(event_user_id)
        if normalized_event_user is None:
            return False
        if normalized_event_user == user_id:
            return True
        if normalized_event_user == 0 and current_user.get("is_admin") is True:
            return True
        return False
    if isinstance(event, MCPNotificationEvent):
        if mcp_server is None:
            raise StateError("MCP server is not available.")
        try:
            client_id = event.client_id
        except AttributeError:
            client_id = None
        if not client_id:
            return False
        session_user_id = mcp_server.session.get_session_user_id(client_id)
        return session_user_id == user_id
    return True
