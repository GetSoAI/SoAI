"""SoAI - Validated manager-layer dependencies [backend/app/composition/build_manager_preconditions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.composition.manager_preconditions import ManagerPreconditions
from app.composition.service_preconditions import require_initialized
from app.types_services_database import DatabaseServices
from app.types_services_foundation import InfrastructureServices, TaskServices

__all__ = ("build_manager_preconditions",)


def build_manager_preconditions(
    infrastructure_services: InfrastructureServices,
    database_services: DatabaseServices,
    task_services: TaskServices,
) -> ManagerPreconditions:
    event_bus = require_initialized(
        infrastructure_services.event_bus,
        message="Event bus must be initialized before managers are built.",
    )
    log_manager = require_initialized(
        infrastructure_services.log_manager,
        message="Log manager must be initialized before managers are built.",
    )
    task_registry = require_initialized(
        task_services.task_registry,
        message="Task registry must be initialized before managers are built.",
    )
    task_registry_queries = require_initialized(
        task_services.task_registry_queries,
        message="Task registry queries must be initialized before managers are built.",
    )
    http_client = require_initialized(
        infrastructure_services.http_client,
        message="HTTP client must be initialized before managers are built.",
    )
    hardware_manager = require_initialized(
        infrastructure_services.hw_manager,
        message="Hardware manager must be initialized before managers are built.",
    )
    command_executor = infrastructure_services.command_executor
    metrics_manager = require_initialized(
        infrastructure_services.metrics_manager,
        message="Metrics manager must be initialized before managers are built.",
    )
    state_aggregator = require_initialized(
        infrastructure_services.state_aggregator,
        message="State aggregator must be initialized before managers are built.",
    )
    authoritative_plugin_state_transitions = require_initialized(
        infrastructure_services.authoritative_plugin_state_transitions,
        message="Authoritative plugin state transition service must be initialized before managers are built.",
    )
    database_core = require_initialized(
        database_services.core,
        message="Database core must be initialized before managers are built.",
    )
    database_models = require_initialized(
        database_services.models,
        message="Database models must be initialized before managers are built.",
    )
    database_plugins = require_initialized(
        database_services.plugins,
        message="Database plugins must be initialized before managers are built.",
    )
    database_hardware = require_initialized(
        database_services.hardware,
        message="Database hardware must be initialized before managers are built.",
    )
    database_users = require_initialized(
        database_services.users,
        message="Database users must be initialized before managers are built.",
    )
    database_tokens = require_initialized(
        database_services.tokens,
        message="Database tokens must be initialized before managers are built.",
    )
    database_api_keys = require_initialized(
        database_services.api_keys,
        message="Database api keys must be initialized before managers are built.",
    )
    database_mcp_access_tokens = require_initialized(
        database_services.mcp_access_tokens,
        message="Database MCP access tokens must be initialized before managers are built.",
    )
    database_prompts = require_initialized(
        database_services.prompts,
        message="Database prompts must be initialized before managers are built.",
    )
    database_conversations = require_initialized(
        database_services.conversations,
        message="Database conversations must be initialized before managers are built.",
    )
    database_chat_identity_defaults = require_initialized(
        database_services.chat_identity_defaults,
        message="Database chat identity defaults must be initialized before managers are built.",
    )
    database_chat_model_defaults = require_initialized(
        database_services.chat_model_defaults,
        message="Database chat model defaults must be initialized before managers are built.",
    )
    database_automations = require_initialized(
        database_services.automations,
        message="Database automations must be initialized before managers are built.",
    )
    database_automation_runs = require_initialized(
        database_services.automation_runs,
        message="Database automation runs must be initialized before managers are built.",
    )
    database_messages = require_initialized(
        database_services.messages,
        message="Database messages must be initialized before managers are built.",
    )
    database_messaging_accounts = require_initialized(
        database_services.messaging_accounts,
        message="Database Messaging accounts must be initialized before managers are built.",
    )
    database_messaging_ingress = require_initialized(
        database_services.messaging_ingress,
        message="Database Messaging ingress must be initialized before managers are built.",
    )
    database_messaging_deliveries = require_initialized(
        database_services.messaging_deliveries,
        message="Database Messaging deliveries must be initialized before managers are built.",
    )
    database_notifications = require_initialized(
        database_services.notifications,
        message="Database notifications must be initialized before managers are built.",
    )
    database_tool_calls = require_initialized(
        database_services.tool_calls,
        message="Database tool calls must be initialized before managers are built.",
    )
    database_files = require_initialized(
        database_services.files,
        message="Database files must be initialized before managers are built.",
    )
    database_knowledge_prompt_state = require_initialized(
        database_services.knowledge_prompt_state,
        message="Knowledge prompt state database must be initialized before managers are built.",
    )
    database_tasks = require_initialized(
        database_services.tasks,
        message="Database tasks must be initialized before managers are built.",
    )
    database_mcp = require_initialized(
        database_services.model_context_protocol,
        message="Model Context Protocol database must be initialized before managers are built.",
    )
    database_memory = require_initialized(
        database_services.memory,
        message="Memory database must be initialized before managers are built.",
    )
    database_agent_event_sequences = require_initialized(
        database_services.agent_event_sequences,
        message="Agent event sequence repository must be initialized before managers are built.",
    )
    database_agent_todo_state = require_initialized(
        database_services.agent_todo_state,
        message="Agent todo state repository must be initialized before managers are built.",
    )
    database_agent_plan = require_initialized(
        database_services.agent_plan,
        message="Agent plan repository must be initialized before managers are built.",
    )
    cancellation_coordinator = require_initialized(
        task_services.cancellation_coordinator,
        message="Cancellation coordinator must be initialized before managers are built.",
    )
    cancellation_history = require_initialized(
        task_services.cancellation_history,
        message="Cancellation history must be initialized before managers are built.",
    )
    cancellation_event_bus = require_initialized(
        task_services.cancellation_event_bus,
        message="Cancellation event bus must be initialized before managers are built.",
    )
    token_collection = require_initialized(
        task_services.token_collection,
        message="Token collection must be initialized before managers are built.",
    )
    cancellation_binder = require_initialized(
        task_services.task_cancellation_binder,
        message="Task cancellation binder must be initialized before managers are built.",
    )
    finalizer_tracker = require_initialized(
        task_services.task_finalizer_tracker,
        message="Task finalizer tracker must be initialized before managers are built.",
    )
    return ManagerPreconditions(
        event_bus=event_bus,
        log_manager=log_manager,
        task_registry=task_registry,
        task_registry_queries=task_registry_queries,
        http_client=http_client,
        hardware_manager=hardware_manager,
        command_executor=command_executor,
        metrics_manager=metrics_manager,
        state_aggregator=state_aggregator,
        authoritative_plugin_state_transitions=authoritative_plugin_state_transitions,
        database_core=database_core,
        database_models=database_models,
        database_plugins=database_plugins,
        database_hardware=database_hardware,
        database_users=database_users,
        database_tokens=database_tokens,
        database_api_keys=database_api_keys,
        database_mcp_access_tokens=database_mcp_access_tokens,
        database_prompts=database_prompts,
        database_conversations=database_conversations,
        database_chat_identity_defaults=database_chat_identity_defaults,
        database_chat_model_defaults=database_chat_model_defaults,
        database_automations=database_automations,
        database_automation_runs=database_automation_runs,
        database_messages=database_messages,
        database_messaging_accounts=database_messaging_accounts,
        database_messaging_ingress=database_messaging_ingress,
        database_messaging_deliveries=database_messaging_deliveries,
        database_notifications=database_notifications,
        database_password_vault=database_services.password_vault,
        database_tool_calls=database_tool_calls,
        database_read_video=database_services.read_video,
        database_files=database_files,
        database_conversation_knowledge_attachments=(
            database_services.conversation_knowledge_attachments
        ),
        database_knowledge_prompt_state=database_knowledge_prompt_state,
        database_tasks=database_tasks,
        database_mcp=database_mcp,
        database_memory=database_memory,
        database_agent_event_sequences=database_agent_event_sequences,
        database_agent_todo_state=database_agent_todo_state,
        database_agent_plan=database_agent_plan,
        cancellation_coordinator=cancellation_coordinator,
        cancellation_history=cancellation_history,
        cancellation_event_bus=cancellation_event_bus,
        token_collection=token_collection,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
    )
