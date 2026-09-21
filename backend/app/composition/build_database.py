"""SoAI - Database subsystem composition helpers [backend/app/composition/build_database.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.composition.create_configured_database_core import (
    create_configured_database_core,
)
from app.lifecycle.coordinator import LifecycleCoordinator
from app.lifecycle.database_shutdown_entries import (
    cleanup_database_core_after_build_failure,
    report_database_build_failure,
)
from app.types_services_database import DatabaseServices
from core.config.protocols import ConfigProtocol
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.logging.trace import get_logger
from core.mutations.storage_composition import MutationStorageComposition
from core.plugins.protocols_instance import FilesProtocol
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.tasks.type_catalog import TaskTypeCatalog
from database.repositories.dependencies import DatabaseRepositoryDependencies
from database.repositories.files.service import DatabaseFiles
from database.repositories.hardware.service import DatabaseHardware
from database.repositories.licensing.service import DatabaseLicensing
from database.repositories.licensing.wizard_service import DatabaseLicensingWizard
from database.repositories.mcp_repository import DatabaseMCP
from database.repositories.memory.service import DatabaseMemory
from database.repositories.metrics.service import DatabaseMetrics
from database.repositories.models.service import DatabaseModels
from database.repositories.openai_chat_completions.service import (
    DatabaseOpenAIChatCompletions,
)
from database.repositories.openai_conversations.service import (
    DatabaseOpenAIConversations,
)
from database.repositories.openai_responses.service import DatabaseOpenAIResponses
from database.repositories.plugins.service import DatabasePlugins
from database.repositories.rag_knowledge_prompt_state import (
    DatabaseKnowledgePromptState,
)
from database.repositories.system.database_operations import (
    DatabaseOperationStatusRepository,
)
from database.repositories.system.power_operations import DatabasePowerOperations
from database.repositories.tasks.query_service import DatabaseTaskQueries
from database.repositories.tasks.service import DatabaseTasks
from database.repositories.users.agent_event_sequences import (
    DatabaseAgentEventSequences,
)
from database.repositories.users.agent_plan import DatabaseAgentPlan
from database.repositories.users.agent_todo_state import DatabaseAgentTodoState
from database.repositories.users.agent_turn_process_boundary import (
    DatabaseAgentTurnProcessBoundary,
)
from database.repositories.users.agent_turns import DatabaseAgentTurns
from database.repositories.users.api_keys.service import DatabaseAPIKeys
from database.repositories.users.automation_occurrence_deletions import (
    DatabaseAutomationOccurrenceDeletions,
)
from database.repositories.users.automation_run_scheduler_repository import (
    DatabaseAutomationRunScheduler,
)
from database.repositories.users.automation_runs.repository import (
    DatabaseAutomationRuns,
)
from database.repositories.users.automations import DatabaseAutomations
from database.repositories.users.calendar.service import DatabaseCalendar
from database.repositories.users.chat_identity_defaults import (
    DatabaseChatIdentityDefaults,
)
from database.repositories.users.chat_model_defaults import DatabaseChatModelDefaults
from database.repositories.users.chat_presets import DatabaseChatPresets
from database.repositories.users.chat_prompt_history import DatabaseChatPromptHistory
from database.repositories.users.conversation_attachments import (
    DatabaseConversationAttachments,
)
from database.repositories.users.conversation_drafts import DatabaseConversationDrafts
from database.repositories.users.conversation_input_execution import (
    DatabaseConversationInputExecution,
)
from database.repositories.users.conversation_inputs import DatabaseConversationInputs
from database.repositories.users.conversation_knowledge_attachments import (
    DatabaseConversationKnowledgeAttachments,
)
from database.repositories.users.conversation_linked_knowledge import (
    DatabaseConversationLinkedKnowledge,
)
from database.repositories.users.conversation_regenerations import (
    DatabaseConversationRegenerations,
)
from database.repositories.users.conversation_stream_cancellations import (
    DatabaseConversationStreamCancellations,
)
from database.repositories.users.conversations import DatabaseConversations
from database.repositories.users.external_accounts.service import (
    DatabaseExternalAccounts,
)
from database.repositories.users.identity_mutation_records import DatabaseUserMutations
from database.repositories.users.mail.service import DatabaseMail
from database.repositories.users.mcp_access_tokens.service import (
    DatabaseMcpAccessTokens,
)
from database.repositories.users.messages import DatabaseMessages
from database.repositories.users.messaging_accounts import DatabaseMessagingAccounts
from database.repositories.users.messaging_deliveries import DatabaseMessagingDeliveries
from database.repositories.users.messaging_ingress import DatabaseMessagingIngress
from database.repositories.users.notifications import DatabaseNotifications
from database.repositories.users.password_vault_writes import DatabasePasswordVault
from database.repositories.users.prompts import DatabasePrompts
from database.repositories.users.read_video_repository import DatabaseReadVideoJobs
from database.repositories.users.tokens import DatabaseTokens
from database.repositories.users.tool_calls import DatabaseToolCalls
from database.repositories.users.users import DatabaseUsers

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

__all__ = ("build_database_services",)

LOGGER_NAME = "SoAI.app.composition.build_database"


async def build_database_services(
    *,
    config: ConfigProtocol,
    files: FilesProtocol,
    encryption_key_tuple: tuple[Fernet, ...],
    lifecycle_coordinator: LifecycleCoordinator,
    event_bus: EventBusProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    mutation_storage: MutationStorageComposition,
    task_catalog: TaskTypeCatalog,
) -> DatabaseServices:
    logger = get_logger(LOGGER_NAME)
    database_core = await create_configured_database_core(
        config=config,
        files=files,
        logger=logger,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        task_catalog=task_catalog,
    )
    try:
        await database_core.vacuum.run_startup_maintenance()
        repository_dependencies = DatabaseRepositoryDependencies(
            core=database_core,
            config=config,
            fernet=encryption_key_tuple,
            event_bus=event_bus,
            files=files,
            mutation_storage=mutation_storage,
        )
        lifecycle_coordinator.register_actor(database_core.writer)
        database_models = DatabaseModels(repository_dependencies)
        database_plugins = DatabasePlugins(repository_dependencies)
        database_licensing = DatabaseLicensing(repository_dependencies)
        database_licensing_wizard = DatabaseLicensingWizard(repository_dependencies)
        database_openai_conversations = DatabaseOpenAIConversations(repository_dependencies)
        database_openai_responses = DatabaseOpenAIResponses(repository_dependencies)
        database_openai_chat_completions = DatabaseOpenAIChatCompletions(repository_dependencies)
        user_repos_deps = DatabaseRepositoryDependencies(
            core=database_core,
            config=config,
            fernet=encryption_key_tuple,
            event_bus=event_bus,
            files=files,
        )
        database_users = DatabaseUsers(user_repos_deps)
        database_user_mutations = DatabaseUserMutations(user_repos_deps)
        database_tokens = DatabaseTokens(user_repos_deps)
        await database_user_mutations.maintain_identity_state()
        database_api_keys = await DatabaseAPIKeys.initialize_from_database(
            core=database_core,
            config=config,
            fernet=encryption_key_tuple,
        )
        database_mcp_access_tokens = DatabaseMcpAccessTokens(user_repos_deps)
        database_prompts = DatabasePrompts(user_repos_deps)
        database_conversations = DatabaseConversations(user_repos_deps)
        database_automations = DatabaseAutomations(user_repos_deps)
        database_notifications = DatabaseNotifications(user_repos_deps)
        database_automation_runs = DatabaseAutomationRuns(
            user_repos_deps,
            database_notifications,
        )
        database_automation_occurrence_deletions = DatabaseAutomationOccurrenceDeletions(
            user_repos_deps,
        )
        database_automation_run_scheduler = DatabaseAutomationRunScheduler(
            user_repos_deps,
            database_notifications,
        )
        database_chat_identity_defaults = DatabaseChatIdentityDefaults(user_repos_deps)
        database_chat_model_defaults = DatabaseChatModelDefaults(user_repos_deps)
        database_chat_presets = DatabaseChatPresets(user_repos_deps)
        database_external_accounts = DatabaseExternalAccounts(user_repos_deps)
        database_mail = DatabaseMail(user_repos_deps)
        database_calendar = DatabaseCalendar(user_repos_deps)
        database_tool_calls = DatabaseToolCalls(user_repos_deps)
        database_read_video = DatabaseReadVideoJobs(user_repos_deps)
        database_messaging_accounts = DatabaseMessagingAccounts(user_repos_deps)
        database_messaging_ingress = DatabaseMessagingIngress(user_repos_deps)
        database_messaging_deliveries = DatabaseMessagingDeliveries(user_repos_deps)
        database_agent_turns = DatabaseAgentTurns(user_repos_deps)
        database_agent_turn_process_boundary = DatabaseAgentTurnProcessBoundary(user_repos_deps)
        database_agent_event_sequences = DatabaseAgentEventSequences(user_repos_deps)
        database_agent_todo_state = DatabaseAgentTodoState(user_repos_deps)
        database_agent_plan = DatabaseAgentPlan(user_repos_deps)
        database_conversation_inputs = DatabaseConversationInputs(user_repos_deps)
        database_conversation_input_execution = DatabaseConversationInputExecution(user_repos_deps)
        database_conversation_regenerations = DatabaseConversationRegenerations(user_repos_deps)
        database_stream_cancellations = DatabaseConversationStreamCancellations(user_repos_deps)
        database_chat_prompt_history = DatabaseChatPromptHistory(user_repos_deps)
        database_conversation_drafts = DatabaseConversationDrafts(user_repos_deps)
        database_password_vault = DatabasePasswordVault(user_repos_deps)
        database_messages = DatabaseMessages(user_repos_deps)
        database_conversation_attachments = DatabaseConversationAttachments(repository_dependencies)
        database_conversation_knowledge_attachments = DatabaseConversationKnowledgeAttachments(
            repository_dependencies,
        )
        database_conversation_linked_knowledge = DatabaseConversationLinkedKnowledge(
            repository_dependencies,
        )
        database_files = DatabaseFiles(repository_dependencies)
        database_knowledge_prompt_state = DatabaseKnowledgePromptState(repository_dependencies)
        database_metrics = DatabaseMetrics(repository_dependencies)
        database_hardware = DatabaseHardware(repository_dependencies)
        database_mcp = DatabaseMCP(repository_dependencies)
        database_memory = DatabaseMemory(repository_dependencies)
        database_task_queries = DatabaseTaskQueries(repository_dependencies)
        database_tasks = DatabaseTasks(repository_dependencies)
        database_operation_status = DatabaseOperationStatusRepository(database_core)
        database_power_operations = DatabasePowerOperations(database_core)
        return DatabaseServices(
            core=database_core,
            models=database_models,
            plugins=database_plugins,
            licensing=database_licensing,
            licensing_wizard=database_licensing_wizard,
            openai_conversations=database_openai_conversations,
            openai_responses=database_openai_responses,
            openai_chat_completions=database_openai_chat_completions,
            users=database_users,
            user_mutations=database_user_mutations,
            tokens=database_tokens,
            api_keys=database_api_keys,
            mcp_access_tokens=database_mcp_access_tokens,
            prompts=database_prompts,
            conversations=database_conversations,
            automations=database_automations,
            automation_occurrence_deletions=database_automation_occurrence_deletions,
            automation_run_scheduler=database_automation_run_scheduler,
            automation_runs=database_automation_runs,
            chat_identity_defaults=database_chat_identity_defaults,
            chat_model_defaults=database_chat_model_defaults,
            chat_presets=database_chat_presets,
            external_accounts=database_external_accounts,
            mail=database_mail,
            calendar=database_calendar,
            messages=database_messages,
            conversation_attachments=database_conversation_attachments,
            conversation_knowledge_attachments=database_conversation_knowledge_attachments,
            conversation_linked_knowledge=database_conversation_linked_knowledge,
            messaging_accounts=database_messaging_accounts,
            messaging_ingress=database_messaging_ingress,
            messaging_deliveries=database_messaging_deliveries,
            notifications=database_notifications,
            input_queue=database_conversation_inputs,
            input_execution=database_conversation_input_execution,
            regenerations=database_conversation_regenerations,
            stream_cancellations=database_stream_cancellations,
            chat_prompt_history=database_chat_prompt_history,
            conversation_drafts=database_conversation_drafts,
            password_vault=database_password_vault,
            agent_turns=database_agent_turns,
            agent_turn_process_boundary=database_agent_turn_process_boundary,
            agent_event_sequences=database_agent_event_sequences,
            agent_todo_state=database_agent_todo_state,
            agent_plan=database_agent_plan,
            tool_calls=database_tool_calls,
            read_video=database_read_video,
            files=database_files,
            knowledge_prompt_state=database_knowledge_prompt_state,
            metrics=database_metrics,
            hardware=database_hardware,
            model_context_protocol=database_mcp,
            memory=database_memory,
            task_queries=database_task_queries,
            tasks=database_tasks,
            operation_status=database_operation_status,
            power_operations=database_power_operations,
        )
    except asyncio.CancelledError:
        await cleanup_database_core_after_build_failure(database_core, logger)
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        await report_database_build_failure(database_core, exception, logger)
        raise
