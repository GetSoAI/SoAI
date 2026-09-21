"""SoAI - Database services container dataclass for app composition [backend/app/types_services_database.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies

if TYPE_CHECKING:
    from core.attachments.protocols_database import (
        DatabaseConversationAttachmentsProtocol,
        DatabaseConversationKnowledgeAttachmentsProtocol,
        DatabaseConversationLinkedKnowledgeProtocol,
    )
    from core.auth.protocols_database_api_keys import DatabaseAPIKeysProtocol
    from core.auth.protocols_database_mcp_access_tokens import (
        DatabaseMcpAccessTokensProtocol,
    )
    from core.auth.protocols_database_tokens import DatabaseTokensProtocol
    from core.automation.protocols_database import (
        DatabaseAutomationOccurrenceDeletionsProtocol,
        DatabaseAutomationRunSchedulerProtocol,
        DatabaseAutomationRunsProtocol,
        DatabaseAutomationsProtocol,
    )
    from core.calendar.protocols import DatabaseCalendarProtocol
    from core.chat_presets.protocols import ChatPresetRepositoryProtocol
    from core.conversations.protocols_database_agents import (
        DatabaseAgentEventSequencesProtocol,
        DatabaseAgentPlanProtocol,
        DatabaseAgentTodoStateProtocol,
        DatabaseAgentTurnProcessBoundaryProtocol,
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
    from core.conversations.protocols_database_regenerations import (
        DatabaseConversationRegenerationsProtocol,
    )
    from core.conversations.protocols_database_stream_cancellations import (
        DatabaseConversationStreamCancellationsProtocol,
    )
    from core.database.protocols import DatabaseOperationStatusProtocol
    from core.database.protocols_tasks import DatabaseTasksProtocol
    from core.external_accounts.protocols import DatabaseExternalAccountsProtocol
    from core.files.protocols import DatabaseFilesProtocol
    from core.hardware.protocols import DatabaseHardwareProtocol
    from core.licensing.protocols import (
        LicensingRepositoryProtocol,
        LicensingWizardRepositoryProtocol,
    )
    from core.mail.protocols import DatabaseMailProtocol
    from core.mcp.protocols_storage import DatabaseMCPProtocol
    from core.messaging.protocols import (
        DatabaseMessagingAccountsProtocol,
        DatabaseMessagingDeliveriesProtocol,
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
    from core.read_video.protocols_database import DatabaseReadVideoJobsProtocol
    from core.system.protocols import PowerOperationRepositoryProtocol
    from core.tasks.protocols_query import DatabaseTaskQueriesProtocol
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.users.protocols_database import DatabaseUsersProtocol
    from core.users.protocols_identity_mutations import DatabaseUserMutationsProtocol
    from database.core.core import DatabaseCore
    from database.repositories.memory.service import DatabaseMemory

__all__ = ("DatabaseServices",)


@dataclass(slots=True, frozen=True)
class DatabaseServices:
    core: DatabaseCore
    models: DatabaseModelsProtocol
    plugins: DatabasePluginsProtocol
    licensing: LicensingRepositoryProtocol
    licensing_wizard: LicensingWizardRepositoryProtocol
    openai_conversations: DatabaseOpenAIConversationsProtocol
    openai_responses: DatabaseOpenAIResponsesProtocol
    openai_chat_completions: DatabaseOpenAIChatCompletionsProtocol
    users: DatabaseUsersProtocol
    user_mutations: DatabaseUserMutationsProtocol
    tokens: DatabaseTokensProtocol
    api_keys: DatabaseAPIKeysProtocol
    mcp_access_tokens: DatabaseMcpAccessTokensProtocol
    prompts: DatabasePromptsProtocol
    conversations: DatabaseConversationsProtocol
    automations: DatabaseAutomationsProtocol
    automation_run_scheduler: DatabaseAutomationRunSchedulerProtocol
    automation_runs: DatabaseAutomationRunsProtocol
    automation_occurrence_deletions: DatabaseAutomationOccurrenceDeletionsProtocol
    chat_identity_defaults: DatabaseChatIdentityDefaultsProtocol
    chat_model_defaults: DatabaseChatModelDefaultsProtocol
    chat_presets: ChatPresetRepositoryProtocol
    external_accounts: DatabaseExternalAccountsProtocol
    mail: DatabaseMailProtocol
    calendar: DatabaseCalendarProtocol
    messages: DatabaseMessagesProtocol
    conversation_attachments: DatabaseConversationAttachmentsProtocol
    conversation_knowledge_attachments: DatabaseConversationKnowledgeAttachmentsProtocol
    conversation_linked_knowledge: DatabaseConversationLinkedKnowledgeProtocol
    messaging_accounts: DatabaseMessagingAccountsProtocol
    messaging_ingress: DatabaseMessagingIngressProtocol
    messaging_deliveries: DatabaseMessagingDeliveriesProtocol
    notifications: DatabaseNotificationsProtocol
    input_queue: DatabaseConversationInputsProtocol
    input_execution: DatabaseConversationInputExecutionProtocol
    regenerations: DatabaseConversationRegenerationsProtocol
    stream_cancellations: DatabaseConversationStreamCancellationsProtocol
    chat_prompt_history: DatabaseChatPromptHistoryProtocol
    conversation_drafts: DatabaseConversationDraftsProtocol
    password_vault: DatabasePasswordVaultProtocol
    agent_turns: DatabaseAgentTurnsProtocol
    agent_turn_process_boundary: DatabaseAgentTurnProcessBoundaryProtocol
    agent_event_sequences: DatabaseAgentEventSequencesProtocol
    agent_todo_state: DatabaseAgentTodoStateProtocol
    agent_plan: DatabaseAgentPlanProtocol
    tool_calls: DatabaseToolCallsProtocol
    read_video: DatabaseReadVideoJobsProtocol
    files: DatabaseFilesProtocol
    knowledge_prompt_state: DatabaseKnowledgePromptStateProtocol
    metrics: DatabaseMetricsProtocol
    hardware: DatabaseHardwareProtocol
    model_context_protocol: DatabaseMCPProtocol
    memory: DatabaseMemory
    task_queries: DatabaseTaskQueriesProtocol
    tasks: DatabaseTasksProtocol
    operation_status: DatabaseOperationStatusProtocol
    power_operations: PowerOperationRepositoryProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="DatabaseServices",
            core=self.core,
            models=self.models,
            plugins=self.plugins,
            licensing=self.licensing,
            licensing_wizard=self.licensing_wizard,
            openai_conversations=self.openai_conversations,
            openai_responses=self.openai_responses,
            openai_chat_completions=self.openai_chat_completions,
            users=self.users,
            user_mutations=self.user_mutations,
            tokens=self.tokens,
            api_keys=self.api_keys,
            mcp_access_tokens=self.mcp_access_tokens,
            prompts=self.prompts,
            conversations=self.conversations,
            automations=self.automations,
            automation_occurrence_deletions=self.automation_occurrence_deletions,
            automation_run_scheduler=self.automation_run_scheduler,
            automation_runs=self.automation_runs,
            chat_identity_defaults=self.chat_identity_defaults,
            chat_model_defaults=self.chat_model_defaults,
            chat_presets=self.chat_presets,
            external_accounts=self.external_accounts,
            mail=self.mail,
            calendar=self.calendar,
            messages=self.messages,
            conversation_attachments=self.conversation_attachments,
            conversation_knowledge_attachments=self.conversation_knowledge_attachments,
            conversation_linked_knowledge=self.conversation_linked_knowledge,
            messaging_accounts=self.messaging_accounts,
            messaging_ingress=self.messaging_ingress,
            messaging_deliveries=self.messaging_deliveries,
            notifications=self.notifications,
            input_queue=self.input_queue,
            input_execution=self.input_execution,
            regenerations=self.regenerations,
            stream_cancellations=self.stream_cancellations,
            chat_prompt_history=self.chat_prompt_history,
            conversation_drafts=self.conversation_drafts,
            password_vault=self.password_vault,
            agent_turns=self.agent_turns,
            agent_turn_process_boundary=self.agent_turn_process_boundary,
            agent_event_sequences=self.agent_event_sequences,
            agent_todo_state=self.agent_todo_state,
            agent_plan=self.agent_plan,
            tool_calls=self.tool_calls,
            read_video=self.read_video,
            files=self.files,
            knowledge_prompt_state=self.knowledge_prompt_state,
            metrics=self.metrics,
            hardware=self.hardware,
            model_context_protocol=self.model_context_protocol,
            memory=self.memory,
            task_queries=self.task_queries,
            tasks=self.tasks,
            operation_status=self.operation_status,
            power_operations=self.power_operations,
        )
