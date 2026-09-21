"""SoAI - API dependency container construction and assembly [backend/features/api/runtime/container/container.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exceptions import ValidationError
from features.api.middleware.acl_dependency_context import ACLDependencyContext
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_runtime_singletons import ApiRuntimeSingletons
from features.api.runtime.container.dependencies_contract_validation_runner import (
    validate_api_dependencies_contract,
)
from features.api.runtime.container.internal_protocols import (
    ApiRuntimeServicesBuilderProtocol,
    MainAppInstanceProtocol,
)
from features.api.runtime.container.types import ApiDependencies
from features.api.runtime.context import raise_api_error

__all__ = ("build_api_dependencies",)


def build_api_dependencies(
    main_instance: MainAppInstanceProtocol,
    *,
    build_api_runtime_services: ApiRuntimeServicesBuilderProtocol,
) -> ApiDependencies:
    services = main_instance.services
    runtime = main_instance.runtime
    paths = main_instance.paths
    security = main_instance.security

    if not isinstance(runtime.shutdown_event, asyncio.Event):
        raise ValidationError("runtime.shutdown_event must be an asyncio.Event.")
    if not isinstance(runtime.restart_pending, asyncio.Event):
        raise ValidationError("runtime.restart_pending must be an asyncio.Event.")
    if not isinstance(runtime.startup_ready_event, asyncio.Event):
        raise ValidationError("runtime.startup_ready_event must be an asyncio.Event.")
    if not paths.base_dir:
        raise ValidationError("paths.base_dir is required.")
    if not paths.main_venv_dir:
        raise ValidationError("paths.main_venv_dir is required.")
    restart_state_manager = runtime.restart_state_manager
    if restart_state_manager is None:
        raise ValidationError("runtime.restart_state_manager is required.")
    api_runtime_singletons = main_instance.api_runtime_singletons
    if not isinstance(api_runtime_singletons, ApiRuntimeSingletons):
        raise ValidationError("main_instance.api_runtime_singletons is required.")
    messaging_gateway = services.infrastructure.messaging_gateway
    if messaging_gateway is None:
        raise ValidationError("services.infrastructure.messaging_gateway is required.")
    api_runtime_services = build_api_runtime_services()
    licensing_services = services.licensing
    api_dependencies = ApiDependencies(
        licensing_policy=licensing_services.policy,
        licensing_service=licensing_services.runtime,
        licensing_trust_material=licensing_services.trust_material,
        wizard_licensing_operations=licensing_services.wizard_pending,
        authenticated_licensing_operations=licensing_services.authenticated_activation,
        licensing_maintenance_operations=licensing_services.maintenance,
        licensing_deployment_operations=licensing_services.deployment_operations,
        licensing_administration_operations=licensing_services.administration,
        application_control=main_instance.application_control,
        command_dispatcher=api_runtime_services.command_dispatcher,
        config=services.configuration.config,
        files=services.configuration.files,
        document_reader=services.storage.document_reader,
        parser_registry_factory=services.storage.parser_registry_factory,
        routing_config=services.configuration.routing_config,
        runtime_flags=services.configuration.runtime_flags,
        runtime_state=runtime,
        event_bus=services.infrastructure.event_bus,
        task_registry=services.tasks.task_registry,
        task_registry_queries=services.tasks.task_registry_queries,
        task_type_routing_service=services.tasks.task_type_routing_service,
        cancellation_coordinator=services.tasks.cancellation.coordinator,
        cancellation_history=services.tasks.cancellation.history,
        cancellation_event_bus=services.tasks.cancellation.event_bus,
        token_collection=services.tasks.cancellation.token_collection,
        task_cancellation_binder=services.tasks.cancellation.binder,
        task_finalizer_tracker=services.tasks.cancellation.finalizer_tracker,
        attachment_parse_tasks=api_runtime_singletons.attachment_parse_tasks,
        metrics_manager=services.infrastructure.metrics_manager,
        plugin_manager=services.plugins.plugin_manager,
        hw_manager=services.infrastructure.hardware.manager,
        hw_gpu_tuning=services.infrastructure.hardware.gpu_tuning,
        hardware_control=services.infrastructure.hardware.control,
        hardware_soaibench=services.infrastructure.hardware.soaibench,
        terminal=services.infrastructure.hardware.terminal,
        storage_manager=services.infrastructure.hardware.storage,
        orchestrator_control=services.orchestrator.control,
        orchestrator_lifecycle=services.orchestrator.lifecycle,
        config_manager=services.configuration.config_manager,
        state_aggregator=services.infrastructure.state_aggregator,
        http_client=services.infrastructure.http_client,
        model_resolution_service=services.models.model_resolution_service,
        model_information_service=services.models.model_information_service,
        model_parameter_service=services.models.model_parameter_service,
        model_virtual_model_service=services.models.model_virtual_model_service,
        model_provider_coordinator=services.models.model_provider_coordinator,
        webui_manager=services.plugins.webui_manager,
        log_manager=services.infrastructure.log_manager,
        prompt_token_counter=services.infrastructure.prompt_token_counter,
        agent_chronology_sequencer=api_runtime_services.agent_chronology_sequencer,
        agent_state_service=api_runtime_services.agent_state_service,
        database_plugins=services.databases.plugins,
        database_licensing=services.databases.licensing,
        database_licensing_wizard=services.databases.licensing_wizard,
        database_models=services.databases.models,
        database_openai_conversations=services.databases.openai_conversations,
        database_openai_responses=services.databases.openai_responses,
        database_openai_chat_completions=services.databases.openai_chat_completions,
        database_users=services.databases.users,
        database_user_mutations=services.databases.user_mutations,
        database_tokens=services.databases.tokens,
        database_api_keys=services.databases.api_keys,
        database_prompts=services.databases.prompts,
        database_conversations=services.databases.conversations,
        database_automations=services.databases.automations,
        database_automation_runs=services.databases.automation_runs,
        database_automation_occurrence_deletions=(
            services.databases.automation_occurrence_deletions
        ),
        database_chat_identity_defaults=services.databases.chat_identity_defaults,
        database_chat_model_defaults=services.databases.chat_model_defaults,
        database_chat_presets=services.databases.chat_presets,
        database_messages=services.databases.messages,
        database_conversation_attachments=services.databases.conversation_attachments,
        database_conversation_knowledge_attachments=(
            services.databases.conversation_knowledge_attachments
        ),
        database_conversation_linked_knowledge=services.databases.conversation_linked_knowledge,
        database_notifications=services.databases.notifications,
        database_messaging_accounts=services.databases.messaging_accounts,
        database_messaging_ingress=services.databases.messaging_ingress,
        database_input_queue=services.databases.input_queue,
        database_input_execution=services.databases.input_execution,
        database_regenerations=services.databases.regenerations,
        database_stream_cancellations=services.databases.stream_cancellations,
        database_chat_prompt_history=services.databases.chat_prompt_history,
        database_conversation_drafts=services.databases.conversation_drafts,
        database_password_vault=services.databases.password_vault,
        database_agent_turns=services.databases.agent_turns,
        database_agent_event_sequences=services.databases.agent_event_sequences,
        database_agent_todo_state=services.databases.agent_todo_state,
        database_agent_plan=services.databases.agent_plan,
        database_tool_calls=services.databases.tool_calls,
        database_files=services.databases.files,
        database_knowledge_prompt_state=services.databases.knowledge_prompt_state,
        database_metrics=services.databases.metrics,
        database_hardware=services.databases.hardware,
        database_mcp=services.databases.model_context_protocol,
        database_memory=services.databases.memory,
        database_tasks=services.databases.tasks,
        database_operation_status=services.databases.operation_status,
        messaging_gateway=messaging_gateway,
        secret_handle_store=services.infrastructure.secret_handle_store,
        mcp_server=services.model_context_protocol.coordinator.server,
        mcp_remote=services.model_context_protocol.coordinator.remote,
        mcp_tool_catalog_cache=api_runtime_singletons.mcp_tool_catalog_cache,
        tool_call_processor=services.orchestrator.tool_call_processor,
        auth_config=security.auth_config,
        access_policy_cache=api_runtime_singletons.access_policy_cache,
        proxy_header_anomaly_tracker=api_runtime_singletons.proxy_header_anomaly_tracker,
        security_runtime_state=api_runtime_singletons.security_runtime_state,
        login_attempt_locks=api_runtime_singletons.login_attempt_locks,
        login_password_service=api_runtime_singletons.login_password_service,
        prompts_update_locks=api_runtime_singletons.prompts_update_locks,
        conversation_rag_ingest_locks=api_runtime_singletons.conversation_rag_ingest_locks,
        conversation_agent_settings_locks=api_runtime_singletons.conversation_agent_settings_locks,
        soai_link_resolve_limiter=api_runtime_singletons.soai_link_resolve_limiter,
        enqueue_warning_tracker=api_runtime_singletons.enqueue_warning_tracker,
        multipart_parser_semaphore=api_runtime_singletons.multipart_parser_semaphore,
        provider_video_projection_semaphore=(
            api_runtime_singletons.provider_video_projection_semaphore
        ),
        stream_channel_registry=api_runtime_singletons.stream_channel_registry,
        chat_stream_registry=api_runtime_singletons.chat_stream_registry,
        shutdown_event=runtime.shutdown_event,
        restart_pending=runtime.restart_pending,
        startup_ready_event=runtime.startup_ready_event,
        restart_state_manager=restart_state_manager,
        base_dir=paths.base_dir,
        main_venv_dir=paths.main_venv_dir,
        acl_dependency_context=ACLDependencyContext(
            raise_api_error=raise_api_error,
            log_audit_event=log_audit_event,
        ),
        external_accounts=services.infrastructure.communications.external_accounts,
        mail_accounts=services.infrastructure.communications.mail_accounts,
        calendar_accounts=services.infrastructure.communications.calendar_accounts,
        mail=services.infrastructure.communications.mail,
        calendar=services.infrastructure.communications.calendar,
        conversation_attention=services.infrastructure.conversation_attention,
        power_operation_supervisor=main_instance.power_operation_supervisor,
        host_management_services=services.host_management,
        backup_service=services.storage.backup_service,
        file_explorer_core=services.storage.file_explorer_core,
        file_explorer_batch=services.storage.file_explorer_batch,
        file_explorer_tasks=services.storage.file_explorer_tasks,
        file_explorer_search=services.storage.file_explorer_search,
        file_explorer_download=services.storage.file_explorer_download,
        file_explorer_listings=services.storage.file_explorer_listings,
    )
    validate_api_dependencies_contract(
        base_dir=api_dependencies.base_dir,
        main_venv_dir=api_dependencies.main_venv_dir,
        config=api_dependencies.config,
        files=api_dependencies.files,
    )
    return api_dependencies
