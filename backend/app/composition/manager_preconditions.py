"""SoAI - Manager assembly validated dependency bundle [backend/app/composition/manager_preconditions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx2 import AsyncClient

    from core.attachments.protocols_database import (
        DatabaseConversationKnowledgeAttachmentsProtocol,
    )
    from core.auth.protocols_database_api_keys import DatabaseAPIKeysProtocol
    from core.auth.protocols_database_mcp_access_tokens import (
        DatabaseMcpAccessTokensProtocol,
    )
    from core.auth.protocols_database_tokens import DatabaseTokensProtocol
    from core.automation.protocols_database import (
        DatabaseAutomationRunsProtocol,
        DatabaseAutomationsProtocol,
    )
    from core.conversations.protocols_database_agents import (
        DatabaseAgentEventSequencesProtocol,
        DatabaseAgentPlanProtocol,
        DatabaseAgentTodoStateProtocol,
    )
    from core.conversations.protocols_database_conversation_records import (
        DatabaseConversationsProtocol,
    )
    from core.conversations.protocols_database_conversations import (
        DatabaseMessagesProtocol,
    )
    from core.conversations.protocols_database_defaults import (
        DatabaseChatIdentityDefaultsProtocol,
        DatabaseChatModelDefaultsProtocol,
    )
    from core.conversations.protocols_database_password_vault import (
        DatabasePasswordVaultProtocol,
    )
    from core.database.protocols_tasks import DatabaseTasksProtocol
    from core.events.protocols import EventBusProtocol
    from core.files.protocols import DatabaseFilesProtocol
    from core.hardware.protocols import (
        DatabaseHardwareProtocol,
        HardwareManagerProtocol,
    )
    from core.logging.protocols import LoggingManagerProtocol
    from core.mcp.protocols_storage import DatabaseMCPProtocol
    from core.messaging.protocols import (
        DatabaseMessagingAccountsProtocol,
        DatabaseMessagingDeliveriesProtocol,
        DatabaseMessagingIngressProtocol,
    )
    from core.metrics.protocols import MetricsManagerProtocol
    from core.models.protocols_database import DatabaseModelsProtocol
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.plugins.protocols_database import DatabasePluginsProtocol
    from core.prompts.protocols_database import DatabasePromptsProtocol
    from core.rag.protocols import DatabaseKnowledgePromptStateProtocol
    from core.read_video.protocols_database import DatabaseReadVideoJobsProtocol
    from core.state.protocols import (
        AuthoritativePluginStateTransitionsProtocol,
        StateAggregatorProtocol,
    )
    from core.system.protocols import CommandExecutorProtocol
    from core.tasks.protocols import (
        CancellationCoordinatorProtocol,
        CancellationEventBusProtocol,
        CancellationHistoryProtocol,
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
        TaskRegistryProtocol,
        TokenCollectionProtocol,
    )
    from core.tasks.protocols_query import TaskRegistryQueryView
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.users.protocols_database import DatabaseUsersProtocol
    from database.core.core import DatabaseCore
    from database.repositories.memory.service import DatabaseMemory

__all__ = ("ManagerPreconditions",)


@dataclass(frozen=True, slots=True)
class ManagerPreconditions:
    event_bus: EventBusProtocol
    log_manager: LoggingManagerProtocol
    task_registry: TaskRegistryProtocol
    task_registry_queries: TaskRegistryQueryView
    http_client: AsyncClient
    hardware_manager: HardwareManagerProtocol
    command_executor: CommandExecutorProtocol | None
    metrics_manager: MetricsManagerProtocol
    state_aggregator: StateAggregatorProtocol
    authoritative_plugin_state_transitions: AuthoritativePluginStateTransitionsProtocol
    database_core: DatabaseCore
    database_models: DatabaseModelsProtocol
    database_plugins: DatabasePluginsProtocol
    database_hardware: DatabaseHardwareProtocol
    database_users: DatabaseUsersProtocol
    database_tokens: DatabaseTokensProtocol
    database_api_keys: DatabaseAPIKeysProtocol
    database_mcp_access_tokens: DatabaseMcpAccessTokensProtocol
    database_prompts: DatabasePromptsProtocol
    database_conversations: DatabaseConversationsProtocol
    database_chat_identity_defaults: DatabaseChatIdentityDefaultsProtocol
    database_chat_model_defaults: DatabaseChatModelDefaultsProtocol
    database_automations: DatabaseAutomationsProtocol
    database_automation_runs: DatabaseAutomationRunsProtocol
    database_messages: DatabaseMessagesProtocol
    database_messaging_accounts: DatabaseMessagingAccountsProtocol
    database_messaging_ingress: DatabaseMessagingIngressProtocol
    database_messaging_deliveries: DatabaseMessagingDeliveriesProtocol
    database_notifications: DatabaseNotificationsProtocol
    database_password_vault: DatabasePasswordVaultProtocol
    database_tool_calls: DatabaseToolCallsProtocol
    database_read_video: DatabaseReadVideoJobsProtocol
    database_files: DatabaseFilesProtocol
    database_conversation_knowledge_attachments: DatabaseConversationKnowledgeAttachmentsProtocol
    database_knowledge_prompt_state: DatabaseKnowledgePromptStateProtocol
    database_tasks: DatabaseTasksProtocol
    database_mcp: DatabaseMCPProtocol
    database_memory: DatabaseMemory
    database_agent_event_sequences: DatabaseAgentEventSequencesProtocol
    database_agent_todo_state: DatabaseAgentTodoStateProtocol
    database_agent_plan: DatabaseAgentPlanProtocol
    cancellation_coordinator: CancellationCoordinatorProtocol
    cancellation_history: CancellationHistoryProtocol
    cancellation_event_bus: CancellationEventBusProtocol
    token_collection: TokenCollectionProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
