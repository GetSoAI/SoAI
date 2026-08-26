"""SoAI - Manager precondition unpacking helpers [backend/app/composition/manager_precondition_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.composition.manager_preconditions import ManagerPreconditions

if TYPE_CHECKING:
    from httpx2 import AsyncClient

    from core.auth.protocols_database_api_keys import DatabaseAPIKeysProtocol
    from core.auth.protocols_database_mcp_access_tokens import (
        DatabaseMcpAccessTokensProtocol,
    )
    from core.auth.protocols_database_tokens import DatabaseTokensProtocol
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
    from core.events.protocols import EventBusProtocol
    from core.hardware.protocols import (
        DatabaseHardwareProtocol,
        HardwareManagerProtocol,
    )
    from core.logging.protocols import LoggingManagerProtocol
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

    type InfrastructurePreconditions = tuple[
        "EventBusProtocol",
        "LoggingManagerProtocol",
        "TaskRegistryProtocol",
        "TaskRegistryQueryView",
        "AsyncClient",
        "HardwareManagerProtocol",
        "CommandExecutorProtocol | None",
        "MetricsManagerProtocol",
        "StateAggregatorProtocol",
        "AuthoritativePluginStateTransitionsProtocol",
    ]
    type DatabasePreconditions = tuple[
        "DatabaseModelsProtocol",
        "DatabasePluginsProtocol",
        "DatabaseHardwareProtocol",
        "DatabaseUsersProtocol",
        "DatabaseTokensProtocol",
        "DatabaseAPIKeysProtocol",
        "DatabaseMcpAccessTokensProtocol",
        "DatabasePromptsProtocol",
        "DatabaseConversationsProtocol",
        "DatabaseChatIdentityDefaultsProtocol",
        "DatabaseChatModelDefaultsProtocol",
        "DatabaseMessagesProtocol",
        "DatabaseMessagingAccountsProtocol",
        "DatabaseMessagingIngressProtocol",
        "DatabaseMessagingDeliveriesProtocol",
        "DatabaseNotificationsProtocol",
        "DatabaseToolCallsProtocol",
    ]
    type CancellationPreconditions = tuple[
        "CancellationCoordinatorProtocol",
        "CancellationHistoryProtocol",
        "CancellationEventBusProtocol",
        "TokenCollectionProtocol",
        "TaskCancellationBinderProtocol",
        "TaskFinalizerTrackerProtocol",
    ]

__all__ = (
    "resolve_cancellation_preconditions",
    "resolve_database_preconditions",
    "resolve_infrastructure_preconditions",
)


def resolve_infrastructure_preconditions(
    preconditions: ManagerPreconditions,
) -> InfrastructurePreconditions:
    return (
        preconditions.event_bus,
        preconditions.log_manager,
        preconditions.task_registry,
        preconditions.task_registry_queries,
        preconditions.http_client,
        preconditions.hardware_manager,
        preconditions.command_executor,
        preconditions.metrics_manager,
        preconditions.state_aggregator,
        preconditions.authoritative_plugin_state_transitions,
    )


def resolve_database_preconditions(
    preconditions: ManagerPreconditions,
) -> DatabasePreconditions:
    return (
        preconditions.database_models,
        preconditions.database_plugins,
        preconditions.database_hardware,
        preconditions.database_users,
        preconditions.database_tokens,
        preconditions.database_api_keys,
        preconditions.database_mcp_access_tokens,
        preconditions.database_prompts,
        preconditions.database_conversations,
        preconditions.database_chat_identity_defaults,
        preconditions.database_chat_model_defaults,
        preconditions.database_messages,
        preconditions.database_messaging_accounts,
        preconditions.database_messaging_ingress,
        preconditions.database_messaging_deliveries,
        preconditions.database_notifications,
        preconditions.database_tool_calls,
    )


def resolve_cancellation_preconditions(
    preconditions: ManagerPreconditions,
) -> CancellationPreconditions:
    return (
        preconditions.cancellation_coordinator,
        preconditions.cancellation_history,
        preconditions.cancellation_event_bus,
        preconditions.token_collection,
        preconditions.cancellation_binder,
        preconditions.finalizer_tracker,
    )
