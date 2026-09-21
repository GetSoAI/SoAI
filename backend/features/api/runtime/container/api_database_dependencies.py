"""SoAI - API runtime container database dependency bundle [backend/features/api/runtime/container/api_database_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.attachments.protocols_database import (
    DatabaseConversationAttachmentsProtocol,
    DatabaseConversationKnowledgeAttachmentsProtocol,
    DatabaseConversationLinkedKnowledgeProtocol,
)
from core.auth.protocols_database_api_keys import DatabaseAPIKeysProtocol
from core.auth.protocols_database_tokens import DatabaseTokensProtocol
from core.automation.protocols_database import (
    DatabaseAutomationOccurrenceDeletionsProtocol,
    DatabaseAutomationRunsProtocol,
    DatabaseAutomationsProtocol,
)
from core.chat_presets.protocols import ChatPresetRepositoryProtocol
from core.conversations.protocols_database_agents import (
    DatabaseAgentEventSequencesProtocol,
    DatabaseAgentPlanProtocol,
    DatabaseAgentTodoStateProtocol,
    DatabaseAgentTurnsProtocol,
)
from core.conversations.protocols_database_chat_prompt_history import (
    DatabaseChatPromptHistoryProtocol,
)
from core.conversations.protocols_database_conversation_drafts import (
    DatabaseConversationDraftsProtocol,
)
from core.conversations.protocols_database_conversation_input_execution import (
    DatabaseConversationInputExecutionProtocol,
)
from core.conversations.protocols_database_conversation_inputs import (
    DatabaseConversationInputsProtocol,
)
from core.conversations.protocols_database_conversation_records import (
    DatabaseConversationsProtocol,
)
from core.conversations.protocols_database_conversations import DatabaseMessagesProtocol
from core.conversations.protocols_database_defaults import (
    DatabaseChatIdentityDefaultsProtocol,
    DatabaseChatModelDefaultsProtocol,
)
from core.conversations.protocols_database_password_vault import (
    DatabasePasswordVaultProtocol,
)
from core.conversations.protocols_database_regenerations import (
    DatabaseConversationRegenerationsProtocol,
)
from core.conversations.protocols_database_stream_cancellations import (
    DatabaseConversationStreamCancellationsProtocol,
)
from core.database.protocols import DatabaseOperationStatusProtocol
from core.database.protocols_tasks import DatabaseTasksProtocol
from core.di.validation import require_dependencies
from core.files.protocols import DatabaseFilesProtocol
from core.hardware.protocols import DatabaseHardwareProtocol
from core.licensing.protocols import (
    LicensingRepositoryProtocol,
    LicensingWizardRepositoryProtocol,
)
from core.mcp.protocols_storage import DatabaseMCPProtocol, DatabaseMemoryProtocol
from core.messaging.protocols import (
    DatabaseMessagingAccountsProtocol,
    DatabaseMessagingIngressProtocol,
)
from core.metrics.protocols import DatabaseMetricsProtocol
from core.models.protocols_database import DatabaseModelsProtocol
from core.notifications.protocols_database import DatabaseNotificationsProtocol
from core.openai.protocols_database_chat_completions import (
    DatabaseOpenAIChatCompletionsProtocol,
)
from core.openai.protocols_database_conversations import (
    DatabaseOpenAIConversationsProtocol,
)
from core.openai.protocols_database_responses import DatabaseOpenAIResponsesProtocol
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.prompts.protocols_database import DatabasePromptsProtocol
from core.rag.protocols import DatabaseKnowledgePromptStateProtocol
from core.tool_calls.protocols import DatabaseToolCallsProtocol
from core.users.protocols_database import DatabaseUsersProtocol
from core.users.protocols_identity_mutations import DatabaseUserMutationsProtocol

__all__ = ("ApiDatabaseDependencies",)


@dataclass(frozen=True, slots=True)
class ApiDatabaseDependencies:
    database_plugins: DatabasePluginsProtocol
    database_licensing: LicensingRepositoryProtocol
    database_licensing_wizard: LicensingWizardRepositoryProtocol
    database_models: DatabaseModelsProtocol
    database_openai_responses: DatabaseOpenAIResponsesProtocol
    database_openai_chat_completions: DatabaseOpenAIChatCompletionsProtocol
    database_users: DatabaseUsersProtocol
    database_user_mutations: DatabaseUserMutationsProtocol
    database_tokens: DatabaseTokensProtocol
    database_api_keys: DatabaseAPIKeysProtocol
    database_prompts: DatabasePromptsProtocol
    database_conversations: DatabaseConversationsProtocol
    database_automations: DatabaseAutomationsProtocol
    database_automation_runs: DatabaseAutomationRunsProtocol
    database_automation_occurrence_deletions: DatabaseAutomationOccurrenceDeletionsProtocol
    database_chat_identity_defaults: DatabaseChatIdentityDefaultsProtocol
    database_chat_model_defaults: DatabaseChatModelDefaultsProtocol
    database_chat_presets: ChatPresetRepositoryProtocol
    database_messages: DatabaseMessagesProtocol
    database_conversation_attachments: DatabaseConversationAttachmentsProtocol
    database_conversation_knowledge_attachments: DatabaseConversationKnowledgeAttachmentsProtocol
    database_conversation_linked_knowledge: DatabaseConversationLinkedKnowledgeProtocol
    database_notifications: DatabaseNotificationsProtocol
    database_messaging_accounts: DatabaseMessagingAccountsProtocol
    database_messaging_ingress: DatabaseMessagingIngressProtocol
    database_input_queue: DatabaseConversationInputsProtocol
    database_input_execution: DatabaseConversationInputExecutionProtocol
    database_regenerations: DatabaseConversationRegenerationsProtocol
    database_stream_cancellations: DatabaseConversationStreamCancellationsProtocol
    database_chat_prompt_history: DatabaseChatPromptHistoryProtocol
    database_conversation_drafts: DatabaseConversationDraftsProtocol
    database_password_vault: DatabasePasswordVaultProtocol
    database_agent_turns: DatabaseAgentTurnsProtocol
    database_agent_event_sequences: DatabaseAgentEventSequencesProtocol
    database_agent_todo_state: DatabaseAgentTodoStateProtocol
    database_agent_plan: DatabaseAgentPlanProtocol
    database_tool_calls: DatabaseToolCallsProtocol
    database_files: DatabaseFilesProtocol
    database_knowledge_prompt_state: DatabaseKnowledgePromptStateProtocol
    database_metrics: DatabaseMetricsProtocol
    database_hardware: DatabaseHardwareProtocol
    database_mcp: DatabaseMCPProtocol
    database_memory: DatabaseMemoryProtocol
    database_tasks: DatabaseTasksProtocol
    database_openai_conversations: DatabaseOpenAIConversationsProtocol
    database_operation_status: DatabaseOperationStatusProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApiDatabaseDependencies",
            database_agent_turns=self.database_agent_turns,
            database_agent_event_sequences=self.database_agent_event_sequences,
            database_agent_todo_state=self.database_agent_todo_state,
            database_agent_plan=self.database_agent_plan,
            database_api_keys=self.database_api_keys,
            database_automation_occurrence_deletions=(
                self.database_automation_occurrence_deletions
            ),
            database_automation_runs=self.database_automation_runs,
            database_automations=self.database_automations,
            database_chat_identity_defaults=self.database_chat_identity_defaults,
            database_chat_model_defaults=self.database_chat_model_defaults,
            database_chat_presets=self.database_chat_presets,
            database_conversations=self.database_conversations,
            database_files=self.database_files,
            database_knowledge_prompt_state=self.database_knowledge_prompt_state,
            database_hardware=self.database_hardware,
            database_input_queue=self.database_input_queue,
            database_input_execution=self.database_input_execution,
            database_regenerations=self.database_regenerations,
            database_stream_cancellations=self.database_stream_cancellations,
            database_chat_prompt_history=self.database_chat_prompt_history,
            database_conversation_drafts=self.database_conversation_drafts,
            database_mcp=self.database_mcp,
            database_memory=self.database_memory,
            database_messages=self.database_messages,
            database_conversation_attachments=self.database_conversation_attachments,
            database_conversation_knowledge_attachments=(
                self.database_conversation_knowledge_attachments
            ),
            database_conversation_linked_knowledge=self.database_conversation_linked_knowledge,
            database_metrics=self.database_metrics,
            database_models=self.database_models,
            database_notifications=self.database_notifications,
            database_messaging_accounts=self.database_messaging_accounts,
            database_messaging_ingress=self.database_messaging_ingress,
            database_openai_conversations=self.database_openai_conversations,
            database_openai_responses=self.database_openai_responses,
            database_openai_chat_completions=self.database_openai_chat_completions,
            database_operation_status=self.database_operation_status,
            database_password_vault=self.database_password_vault,
            database_plugins=self.database_plugins,
            database_licensing=self.database_licensing,
            database_licensing_wizard=self.database_licensing_wizard,
            database_prompts=self.database_prompts,
            database_tasks=self.database_tasks,
            database_tokens=self.database_tokens,
            database_tool_calls=self.database_tool_calls,
            database_users=self.database_users,
            database_user_mutations=self.database_user_mutations,
        )
