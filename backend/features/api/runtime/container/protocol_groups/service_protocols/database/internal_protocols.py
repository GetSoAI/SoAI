"""SoAI - Database services internal protocols [backend/features/api/runtime/container/protocol_groups/service_protocols/database/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
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
    from core.conversations.protocols_database_conversation_inputs import (
        DatabaseConversationInputsProtocol,
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
    from core.database.protocols import DatabaseOperationStatusProtocol
    from core.database.protocols_tasks import DatabaseTasksProtocol
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

__all__ = ("DatabaseServicesProtocol",)


class DatabaseServicesProtocol(Protocol):
    @property
    def licensing(self) -> LicensingRepositoryProtocol: ...

    @property
    def licensing_wizard(self) -> LicensingWizardRepositoryProtocol: ...

    @property
    def operation_status(self) -> DatabaseOperationStatusProtocol: ...

    @property
    def tasks(self) -> DatabaseTasksProtocol: ...

    @property
    def tool_calls(self) -> DatabaseToolCallsProtocol: ...

    @property
    def openai_conversations(self) -> DatabaseOpenAIConversationsProtocol: ...

    @property
    def openai_responses(self) -> DatabaseOpenAIResponsesProtocol: ...

    @property
    def openai_chat_completions(self) -> DatabaseOpenAIChatCompletionsProtocol: ...

    @property
    def metrics(self) -> DatabaseMetricsProtocol: ...

    @property
    def plugins(self) -> DatabasePluginsProtocol: ...

    @property
    def models(self) -> DatabaseModelsProtocol: ...

    @property
    def files(self) -> DatabaseFilesProtocol: ...

    @property
    def knowledge_prompt_state(self) -> DatabaseKnowledgePromptStateProtocol: ...

    @property
    def model_context_protocol(self) -> DatabaseMCPProtocol: ...

    @property
    def memory(self) -> DatabaseMemoryProtocol: ...

    @property
    def users(self) -> DatabaseUsersProtocol: ...

    @property
    def user_mutations(self) -> DatabaseUserMutationsProtocol: ...

    @property
    def api_keys(self) -> DatabaseAPIKeysProtocol: ...

    @property
    def conversations(self) -> DatabaseConversationsProtocol: ...

    @property
    def automations(self) -> DatabaseAutomationsProtocol: ...

    @property
    def automation_runs(self) -> DatabaseAutomationRunsProtocol: ...

    @property
    def automation_occurrence_deletions(self) -> DatabaseAutomationOccurrenceDeletionsProtocol: ...

    @property
    def messages(self) -> DatabaseMessagesProtocol: ...

    @property
    def conversation_attachments(self) -> DatabaseConversationAttachmentsProtocol: ...

    @property
    def conversation_knowledge_attachments(
        self,
    ) -> DatabaseConversationKnowledgeAttachmentsProtocol: ...

    @property
    def conversation_linked_knowledge(self) -> DatabaseConversationLinkedKnowledgeProtocol: ...

    @property
    def notifications(self) -> DatabaseNotificationsProtocol: ...

    @property
    def messaging_accounts(self) -> DatabaseMessagingAccountsProtocol: ...

    @property
    def messaging_ingress(self) -> DatabaseMessagingIngressProtocol: ...

    @property
    def tokens(self) -> DatabaseTokensProtocol: ...

    @property
    def prompts(self) -> DatabasePromptsProtocol: ...

    @property
    def input_queue(self) -> DatabaseConversationInputsProtocol: ...

    @property
    def chat_prompt_history(self) -> DatabaseChatPromptHistoryProtocol: ...

    @property
    def conversation_drafts(self) -> DatabaseConversationDraftsProtocol: ...

    @property
    def password_vault(self) -> DatabasePasswordVaultProtocol: ...

    @property
    def agent_event_sequences(self) -> DatabaseAgentEventSequencesProtocol: ...

    @property
    def agent_turns(self) -> DatabaseAgentTurnsProtocol: ...

    @property
    def agent_todo_state(self) -> DatabaseAgentTodoStateProtocol: ...

    @property
    def agent_plan(self) -> DatabaseAgentPlanProtocol: ...

    @property
    def chat_identity_defaults(self) -> DatabaseChatIdentityDefaultsProtocol: ...

    @property
    def chat_model_defaults(self) -> DatabaseChatModelDefaultsProtocol: ...

    @property
    def chat_presets(self) -> ChatPresetRepositoryProtocol: ...

    @property
    def hardware(self) -> DatabaseHardwareProtocol: ...
