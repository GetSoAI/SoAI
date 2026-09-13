"""SoAI - API runtime container dependency bundles [backend/features/api/runtime/container/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

import httpx2

from core.agent.protocols import AgentChronologySequencerProtocol, AgentStateServiceProtocol
from core.app.protocols import ApplicationControlProtocol
from core.calendar.protocols import CalendarServiceProtocol
from core.concurrency.protocols import AsyncLockRegistryProtocol
from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.events.protocols import EventBusProtocol
from core.events.types_base import Event
from core.external_accounts.linked_account_types import LinkedAccountCapabilities
from core.external_accounts.protocols import ExternalAccountsServiceProtocol
from core.features.protocols import CommandDispatcherProtocol
from core.files.protocols import (
    DocumentReaderProtocol,
    FileExplorerBatchProtocol,
    FileExplorerCoreProtocol,
    FileExplorerDownloadProtocol,
    FileExplorerListingProtocol,
    FileExplorerSearchProtocol,
    FileExplorerTaskLauncherProtocol,
    FileParserRegistryFactoryProtocol,
    FilesPathResolverProtocol,
)
from core.hardware.protocols import (
    HardwareControlServiceProtocol,
    HardwareGpuTuningProtocol,
    HardwareManagerProtocol,
)
from core.hardware.protocols_soaibench import SoAIBenchServiceProtocol
from core.hardware.protocols_storage import StorageManagerProtocol
from core.licensing.policy import EditionLicensingPolicy
from core.licensing.protocols import LicensingStatusProtocol
from core.licensing.trust_material import ReleaseTrustMaterial
from core.logging.protocols import LoggingManagerProtocol
from core.mail.protocols import MailServiceProtocol
from core.mcp.protocols_main import MCPRemoteProtocol, MCPServerProtocol
from core.mcp.tool_catalog_cache import MCPToolCatalogCache
from core.messaging.gateway.protocols import MessagingGatewayProtocol
from core.metrics.protocols import MetricsManagerProtocol
from core.notifications.protocols import ConversationAttentionCoordinatorProtocol
from core.orchestrator.routing_config import RoutingConfig
from core.runtime.protocols import RuntimeFlagsViewProtocol, RuntimeHealthViewProtocol
from core.state.access_policy import AccessPolicyCache
from core.state.protocols import RestartStateManagerProtocol
from core.system.protocols import PowerOperationSupervisorProtocol
from core.tasks.protocols import (
    CancellationCoordinatorProtocol,
    CancellationEventBusProtocol,
    CancellationHistoryProtocol,
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    TaskRegistryProtocol,
    TaskTypeRoutingServiceProtocol,
    TokenCollectionProtocol,
)
from core.tasks.protocols_query import TaskRegistryQueryView
from core.terminal.protocols import TerminalServiceProtocol
from core.tool_calls.protocols import ToolCallProcessingProtocol
from core.webui_manager.protocols import WebUIManagerProtocol
from features.api.middleware.acl_dependency_context import ACLDependencyContext
from features.api.middleware.security.types import ProxyHeaderAnomalyTracker
from features.api.runtime.container.api_database_dependencies import ApiDatabaseDependencies
from features.api.runtime.container.auth_config import AuthConfig
from features.api.runtime.container.enqueue_warning_tracker import EnqueueWarningTracker
from features.api.runtime.container.security_runtime_state import SecurityRuntimeState
from features.api.runtime.container.soai_link_resolve_limiter import (
    SoaiLinkResolveConcurrencyLimiter,
)
from features.api.runtime.internal_protocols import (
    BackupServiceProtocol,
    ChatStreamRegistryProtocol,
)
from features.api.streaming.internal_protocols import TaskStreamChannelRegistryProtocol
from features.licensing.administration_operations import LicensingAdministrationOperations
from features.licensing.deployment_operations import LicensingDeploymentOperations
from features.licensing.maintenance_operations import LicensingMaintenanceOperations
from features.licensing.wizard_operations import WizardLicensingOperations

if TYPE_CHECKING:
    from core.config.protocols import ConfigManagerProtocol
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelParameterServiceProtocol,
        ModelProviderCoordinatorProtocol,
        ModelResolutionServiceProtocol,
        VirtualModelServiceProtocol,
    )
    from core.openai.token_counter import PromptTokenCounter
    from core.orchestrator.protocols_lifecycle import (
        OrchestratorControlProtocol,
        OrchestratorLifecycleProtocol,
    )
    from core.os.protocols import HostManagementServicesProtocol
    from core.plugins.protocols import PluginManagerProtocol
    from core.secrets.handle_store import SecretHandleStore
    from core.security.protocols import PasswordServiceProtocol
    from core.state.protocols import StateAggregatorProtocol
    from features.api.runtime.internal_protocols import AttachmentParseTaskRegistryProtocol
__all__ = ("ApiDependencies",)


@dataclass(frozen=True, slots=True)
class ApiDependencies(ApiDatabaseDependencies):
    licensing_policy: EditionLicensingPolicy
    licensing_service: LicensingStatusProtocol
    licensing_trust_material: ReleaseTrustMaterial
    wizard_licensing_operations: WizardLicensingOperations
    authenticated_licensing_operations: WizardLicensingOperations
    licensing_maintenance_operations: LicensingMaintenanceOperations
    licensing_deployment_operations: LicensingDeploymentOperations
    licensing_administration_operations: LicensingAdministrationOperations
    application_control: ApplicationControlProtocol
    command_dispatcher: CommandDispatcherProtocol[Event]
    config: ConfigProtocol
    files: FilesPathResolverProtocol
    document_reader: DocumentReaderProtocol
    parser_registry_factory: FileParserRegistryFactoryProtocol
    routing_config: RoutingConfig
    runtime_flags: RuntimeFlagsViewProtocol
    runtime_state: RuntimeHealthViewProtocol
    event_bus: EventBusProtocol
    task_registry: TaskRegistryProtocol
    task_registry_queries: TaskRegistryQueryView
    task_type_routing_service: TaskTypeRoutingServiceProtocol
    cancellation_coordinator: CancellationCoordinatorProtocol
    cancellation_history: CancellationHistoryProtocol
    cancellation_event_bus: CancellationEventBusProtocol
    token_collection: TokenCollectionProtocol
    task_cancellation_binder: TaskCancellationBinderProtocol
    task_finalizer_tracker: TaskFinalizerTrackerProtocol
    attachment_parse_tasks: AttachmentParseTaskRegistryProtocol
    metrics_manager: MetricsManagerProtocol
    plugin_manager: PluginManagerProtocol
    hw_manager: HardwareManagerProtocol
    hw_gpu_tuning: HardwareGpuTuningProtocol
    hardware_control: HardwareControlServiceProtocol
    hardware_soaibench: SoAIBenchServiceProtocol
    terminal: TerminalServiceProtocol
    storage_manager: StorageManagerProtocol
    orchestrator_control: OrchestratorControlProtocol
    orchestrator_lifecycle: OrchestratorLifecycleProtocol
    config_manager: ConfigManagerProtocol
    state_aggregator: StateAggregatorProtocol
    http_client: httpx2.AsyncClient
    model_resolution_service: ModelResolutionServiceProtocol
    model_information_service: ModelInformationServiceProtocol
    model_parameter_service: ModelParameterServiceProtocol
    model_virtual_model_service: VirtualModelServiceProtocol
    model_provider_coordinator: ModelProviderCoordinatorProtocol
    webui_manager: WebUIManagerProtocol
    log_manager: LoggingManagerProtocol
    prompt_token_counter: PromptTokenCounter
    agent_chronology_sequencer: AgentChronologySequencerProtocol
    agent_state_service: AgentStateServiceProtocol
    messaging_gateway: MessagingGatewayProtocol
    secret_handle_store: SecretHandleStore
    mcp_server: MCPServerProtocol
    mcp_remote: MCPRemoteProtocol
    mcp_tool_catalog_cache: MCPToolCatalogCache
    tool_call_processor: ToolCallProcessingProtocol
    auth_config: AuthConfig
    access_policy_cache: AccessPolicyCache
    proxy_header_anomaly_tracker: ProxyHeaderAnomalyTracker
    security_runtime_state: SecurityRuntimeState
    login_attempt_locks: AsyncLockRegistryProtocol[str]
    login_password_service: PasswordServiceProtocol
    prompts_update_locks: AsyncLockRegistryProtocol[int]
    conversation_rag_ingest_locks: AsyncLockRegistryProtocol[str]
    conversation_agent_settings_locks: AsyncLockRegistryProtocol[tuple[int, str]]
    soai_link_resolve_limiter: SoaiLinkResolveConcurrencyLimiter
    enqueue_warning_tracker: EnqueueWarningTracker
    multipart_parser_semaphore: asyncio.Semaphore
    provider_video_projection_semaphore: asyncio.Semaphore
    stream_channel_registry: TaskStreamChannelRegistryProtocol
    chat_stream_registry: ChatStreamRegistryProtocol
    shutdown_event: asyncio.Event
    restart_pending: asyncio.Event
    startup_ready_event: asyncio.Event
    restart_state_manager: RestartStateManagerProtocol
    base_dir: str
    main_venv_dir: str
    acl_dependency_context: ACLDependencyContext
    external_accounts: ExternalAccountsServiceProtocol
    mail_accounts: LinkedAccountCapabilities
    calendar_accounts: LinkedAccountCapabilities
    mail: MailServiceProtocol
    calendar: CalendarServiceProtocol
    conversation_attention: ConversationAttentionCoordinatorProtocol
    power_operation_supervisor: PowerOperationSupervisorProtocol
    backup_service: BackupServiceProtocol | None = None
    file_explorer_core: FileExplorerCoreProtocol | None = None
    file_explorer_batch: FileExplorerBatchProtocol | None = None
    file_explorer_tasks: FileExplorerTaskLauncherProtocol | None = None
    file_explorer_search: FileExplorerSearchProtocol | None = None
    file_explorer_download: FileExplorerDownloadProtocol | None = None
    file_explorer_listings: FileExplorerListingProtocol | None = None
    host_management_services: HostManagementServicesProtocol | None = None

    @override
    def __post_init__(self) -> None:
        ApiDatabaseDependencies.__post_init__(self)
        require_dependencies(
            owner="ApiDependencies",
            access_policy_cache=self.access_policy_cache,
            acl_dependency_context=self.acl_dependency_context,
            agent_chronology_sequencer=self.agent_chronology_sequencer,
            agent_state_service=self.agent_state_service,
            application_control=self.application_control,
            attachment_parse_tasks=self.attachment_parse_tasks,
            auth_config=self.auth_config,
            base_dir=self.base_dir,
            calendar=self.calendar,
            calendar_accounts=self.calendar_accounts,
            conversation_attention=self.conversation_attention,
            cancellation_coordinator=self.cancellation_coordinator,
            cancellation_event_bus=self.cancellation_event_bus,
            cancellation_history=self.cancellation_history,
            chat_stream_registry=self.chat_stream_registry,
            command_dispatcher=self.command_dispatcher,
            config=self.config,
            config_manager=self.config_manager,
            document_reader=self.document_reader,
            enqueue_warning_tracker=self.enqueue_warning_tracker,
            event_bus=self.event_bus,
            external_accounts=self.external_accounts,
            files=self.files,
            hardware_control=self.hardware_control,
            hardware_soaibench=self.hardware_soaibench,
            http_client=self.http_client,
            hw_gpu_tuning=self.hw_gpu_tuning,
            hw_manager=self.hw_manager,
            log_manager=self.log_manager,
            login_attempt_locks=self.login_attempt_locks,
            login_password_service=self.login_password_service,
            licensing_policy=self.licensing_policy,
            licensing_service=self.licensing_service,
            licensing_trust_material=self.licensing_trust_material,
            wizard_licensing_operations=self.wizard_licensing_operations,
            authenticated_licensing_operations=self.authenticated_licensing_operations,
            licensing_maintenance_operations=self.licensing_maintenance_operations,
            licensing_deployment_operations=self.licensing_deployment_operations,
            licensing_administration_operations=self.licensing_administration_operations,
            mail=self.mail,
            mail_accounts=self.mail_accounts,
            main_venv_dir=self.main_venv_dir,
            mcp_remote=self.mcp_remote,
            mcp_server=self.mcp_server,
            mcp_tool_catalog_cache=self.mcp_tool_catalog_cache,
            messaging_gateway=self.messaging_gateway,
            metrics_manager=self.metrics_manager,
            model_information_service=self.model_information_service,
            model_parameter_service=self.model_parameter_service,
            model_provider_coordinator=self.model_provider_coordinator,
            model_resolution_service=self.model_resolution_service,
            model_virtual_model_service=self.model_virtual_model_service,
            multipart_parser_semaphore=self.multipart_parser_semaphore,
            provider_video_projection_semaphore=self.provider_video_projection_semaphore,
            orchestrator_control=self.orchestrator_control,
            orchestrator_lifecycle=self.orchestrator_lifecycle,
            parser_registry_factory=self.parser_registry_factory,
            plugin_manager=self.plugin_manager,
            power_operation_supervisor=self.power_operation_supervisor,
            prompt_token_counter=self.prompt_token_counter,
            prompts_update_locks=self.prompts_update_locks,
            conversation_rag_ingest_locks=self.conversation_rag_ingest_locks,
            conversation_agent_settings_locks=self.conversation_agent_settings_locks,
            soai_link_resolve_limiter=self.soai_link_resolve_limiter,
            proxy_header_anomaly_tracker=self.proxy_header_anomaly_tracker,
            restart_pending=self.restart_pending,
            restart_state_manager=self.restart_state_manager,
            routing_config=self.routing_config,
            runtime_state=self.runtime_state,
            runtime_flags=self.runtime_flags,
            security_runtime_state=self.security_runtime_state,
            secret_handle_store=self.secret_handle_store,
            shutdown_event=self.shutdown_event,
            startup_ready_event=self.startup_ready_event,
            state_aggregator=self.state_aggregator,
            storage_manager=self.storage_manager,
            stream_channel_registry=self.stream_channel_registry,
            task_cancellation_binder=self.task_cancellation_binder,
            task_finalizer_tracker=self.task_finalizer_tracker,
            task_registry=self.task_registry,
            task_registry_queries=self.task_registry_queries,
            task_type_routing_service=self.task_type_routing_service,
            terminal=self.terminal,
            token_collection=self.token_collection,
            tool_call_processor=self.tool_call_processor,
            webui_manager=self.webui_manager,
        )
