"""SoAI - Plugin SDK public typing surface [backend/plugin_sdk/__init__.pyi]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.archives.errors import ArchiveLinkTargetNotFoundError
from core.config.protocols import ConfigProtocol
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.memory_exhaustion import (
    classify_memory_exhaustion,
    raise_for_memory_exhaustion,
)
from core.events.protocols import EventBusProtocol
from core.filesystem.async_queries import (
    async_isdir,
    async_isfile,
    async_islink,
    async_listdir,
    async_makedirs,
    async_path_exists,
)
from core.filesystem.hashing import (
    calculate_directory_hash,
    calculate_file_hash,
    calculate_file_hash_sync,
)
from core.filesystem.size_calculation import get_path_size
from core.models.remote_model_search_payloads import normalize_model_search_payload
from core.openai.audio_upload_responses import (
    AUDIO_UPLOAD_ERROR_RESPONSE_MARKER,
    build_audio_upload_error_response,
    is_audio_upload_error_response,
    read_audio_upload_error_response,
)
from core.openai.context_overflow_validation import (
    build_context_overflow_validation_error,
    extract_context_overflow_validation,
)
from core.openai.embedding import (
    merge_embedding_batch_responses,
    prepare_embedding_batches,
    resolve_embedding_batch_limit,
)
from core.openai.endpoint_request_contracts import OpenAIRequestBodyOperation
from core.openai.model_output_contract_errors import (
    build_invalid_tool_call_json_error_details,
    is_invalid_tool_call_json_contract_error,
)
from core.openai.provider_transport import (
    build_openai_provider_headers,
    build_openai_upstream_error_details,
    compose_openai_provider_url,
    normalize_openai_provider_query_params,
)
from core.plugins.backend_variants import (
    AUTO_BACKEND_VARIANT_ID,
    build_auto_backend_variant_option,
    normalize_backend_variant_id,
    require_backend_variant_id,
    resolve_cuda_backend_availability,
)
from core.plugins.protocols_instance import FilesProtocol
from core.plugins.protocols_runtime import (
    PluginHardwareRuntimeProtocol,
    PluginStorageReservationLeaseProtocol,
    PluginStorageRuntimeProtocol,
    PluginStorageWriteClaimProtocol,
)
from core.plugins.runtime_services import (
    PLUGIN_MODULE_PREFIX,
    UNLOAD_ALL_MODELS_SENTINEL,
    PluginPathResolver,
    PluginRuntimeServices,
)
from core.system.commands import run_argv_capture
from core.system.subprocess_env import build_minimal_subprocess_env
from core.tasks.periodic import run_periodic_task
from core.types.json import JSONDict, JSONValue
from core.types.protocols import HttpClientProtocol
from plugin_sdk.config import Config, ConfigError
from plugin_sdk.config_building import build_config, safe_config_float, safe_config_int
from plugin_sdk.contracts.accelerator_environment import build_accelerator_environment
from plugin_sdk.contracts.accelerator_inventory import snapshot_accelerator_inventory
from plugin_sdk.contracts.archive_extraction import (
    async_safe_tar_extractall,
    async_safe_zip_extractall,
)
from plugin_sdk.contracts.chat_template_role_policy import (
    SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER,
    normalize_openai_messages_for_chat_template_role_policy,
    normalize_openai_responses_input_for_chat_template_role_policy,
    prepare_openai_request_for_chat_template_role_policy,
    strip_soai_internal_chat_template_parameters,
)
from plugin_sdk.contracts.config_access import (
    get_config_bool,
    get_config_float,
    get_config_int,
    get_config_str,
)
from plugin_sdk.contracts.downloads import async_stream_download_to_file
from plugin_sdk.contracts.errors import (
    ErrorType,
    PluginConfigurationError,
    error_type_to_status_code,
)
from plugin_sdk.contracts.loopback_listener_processes import (
    LoopbackListenerIdentity,
    LoopbackListenerResolution,
    resolve_verified_loopback_listener_identity,
    terminate_verified_loopback_listener,
)
from plugin_sdk.contracts.metadata import ModelMetadataStore, read_metadata
from plugin_sdk.contracts.model_artifacts import (
    LocalArtifact,
    RemoteArtifact,
    RemoteArtifactFile,
    build_artifact_directory_name,
    build_direct_artifact_directory,
    collect_artifact_directories,
    group_remote_artifact_files,
    inspect_artifact_directory,
    parse_artifact_shard_filename,
)
from plugin_sdk.contracts.model_variants import (
    build_model_variant,
    normalize_variant_name,
    resolve_model_download_required_bytes,
)
from plugin_sdk.contracts.openai import (
    OPENAI_CAPABILITY_CATEGORIES,
    OPENAI_FEATURE_MATRIX,
    ExternalProviderMode,
    OpenAIChatFeature,
    OpenAIEndpoint,
    OpenAIImageFeature,
    OpenAIModality,
    normalize_external_provider_mode,
    normalize_openai_modalities,
    normalize_openai_modalities_strict,
    normalize_openai_modality,
)
from plugin_sdk.contracts.openai_request_payloads import (
    build_openai_upstream_request_body_payload,
    resolve_openai_upstream_custom_request_field_names,
)
from plugin_sdk.contracts.outbound_headers import (
    build_artifact_download_headers,
    build_github_api_headers,
    build_model_registry_headers,
    build_outbound_request_headers,
    merge_outbound_headers,
)
from plugin_sdk.contracts.parameters import (
    ClonableField,
    NoDefault,
    ParameterDefinition,
    build_parameter_schema,
)
from plugin_sdk.contracts.process_diagnostics import read_recent_process_log
from plugin_sdk.contracts.process_lifecycle import check_process_alive
from plugin_sdk.contracts.process_sessions import (
    ManagedProcessSession,
    spawn_logged_process,
    terminate_logged_process,
)
from plugin_sdk.contracts.progress import (
    DownloadProgressReporter,
    DownloadStatsPayload,
    ProgressPayload,
    SpeedCalculator,
    format_progress_bar,
    get_progress_payload,
)
from plugin_sdk.contracts.prompt_token_counting import (
    build_estimated_prompt_token_count_result,
    build_exact_prompt_token_count_result,
    build_unsupported_prompt_token_count_result,
)
from plugin_sdk.contracts.quantization_tokens import extract_quantization_token
from plugin_sdk.contracts.repository_artifacts import (
    build_repository_artifact_directory,
    build_repository_artifact_model_identifier,
    resolve_repository_artifact_model_identifier,
)
from plugin_sdk.contracts.reserved_writes import (
    write_metadata_with_disk_reservation,
    write_text_with_disk_reservation,
    write_text_with_disk_reservation_sync,
)
from plugin_sdk.contracts.safe_paths import resolve_plugin_backend_root, safe_join_under_base
from plugin_sdk.contracts.schema_cli_arguments import build_schema_cli_arguments
from plugin_sdk.contracts.tar_zst_extraction import async_safe_tar_zst_extractall
from plugin_sdk.contracts.transfer import (
    calculate_eta,
    format_eta,
    format_speed,
    format_transfer_details,
    format_transfer_log_suffix,
    format_transfer_size,
    format_transfer_status_message,
)
from plugin_sdk.contracts.version import get_core_version
from plugin_sdk.errors import (
    AcceleratorMemoryExhaustedError,
    ConfigurationError,
    ExternalServiceError,
    FeatureDisabledError,
    ModelOutputContractError,
    NotFoundError,
    ProcessError,
    SecurityError,
    SoAIError,
    StateError,
    SystemMemoryExhaustedError,
    ValidationError,
)
from plugin_sdk.events import ProviderStatusUpdatedEvent
from plugin_sdk.filesystem.directory_creation import (
    ensure_dirs_exist,
    ensure_parent_dirs_exist,
)
from plugin_sdk.filesystem.files import Files
from plugin_sdk.filesystem.removal import async_remove
from plugin_sdk.hf.normalize import normalize_hf_model_input
from plugin_sdk.hf.search import (
    RemoteModelSearchError,
    RemoteModelSearchResult,
    RemoteModelSearchVariant,
    build_model_search_terms,
    hf_model_search,
    resolve_hf_token,
)
from plugin_sdk.protocols import AcceleratorInventoryProviderProtocol
from plugin_sdk.public_exports_type_stubs import (
    BasePlugin,
    enforce_offline_policy,
    require_online_mode,
)
from plugin_sdk.runtime import (
    ModelContext,
    RequestContext,
    Shutdownable,
    create_system_context,
    get_runtime_platform,
    runtime_flags,
)
from plugin_sdk.runtime_network import (
    OfflineModeError,
    create_guarded_async_http_client,
    guard_outbound_http_request,
    is_block_private_network_egress_enabled,
    is_loopback_host,
    is_offline_mode_enabled,
    validate_local_only_url,
    validate_runtime_host_port,
)

__all__ = (
    "AcceleratorMemoryExhaustedError",
    "ArchiveLinkTargetNotFoundError",
    "AUTO_BACKEND_VARIANT_ID",
    "BasePlugin",
    "ClonableField",
    "Config",
    "ConfigProtocol",
    "ConfigError",
    "create_guarded_async_http_client",
    "create_system_context",
    "DownloadProgressReporter",
    "DownloadStatsPayload",
    "coerce_to_soai_error",
    "log_exception",
    "log_handled_exception",
    "ProgressPayload",
    "ProgressTracker",
    "SpeedCalculator",
    "format_progress_bar",
    "get_progress_payload",
    "ErrorType",
    "EventBusProtocol",
    "HttpClientProtocol",
    "check_process_alive",
    "Files",
    "FilesProtocol",
    "JSONDict",
    "JSONValue",
    "ModelContext",
    "OfflineModeError",
    "ModelMetadataStore",
    "NoDefault",
    "ConfigurationError",
    "ExternalProviderMode",
    "ExternalServiceError",
    "OPENAI_CAPABILITY_CATEGORIES",
    "FeatureDisabledError",
    "OPENAI_FEATURE_MATRIX",
    "ModelOutputContractError",
    "OpenAIChatFeature",
    "NotFoundError",
    "OpenAIEndpoint",
    "ProcessError",
    "OpenAIImageFeature",
    "SecurityError",
    "OpenAIModality",
    "SoAIError",
    "normalize_external_provider_mode",
    "StateError",
    "SystemMemoryExhaustedError",
    "normalize_openai_modalities",
    "ValidationError",
    "normalize_openai_modalities_strict",
    "normalize_openai_modality",
    "OpenAIRequestBodyOperation",
    "AUDIO_UPLOAD_ERROR_RESPONSE_MARKER",
    "build_audio_upload_error_response",
    "is_audio_upload_error_response",
    "read_audio_upload_error_response",
    "build_openai_provider_headers",
    "build_exact_prompt_token_count_result",
    "build_estimated_prompt_token_count_result",
    "build_unsupported_prompt_token_count_result",
    "build_context_overflow_validation_error",
    "build_openai_upstream_error_details",
    "compose_openai_provider_url",
    "extract_context_overflow_validation",
    "normalize_openai_provider_query_params",
    "build_artifact_download_headers",
    "build_github_api_headers",
    "build_model_registry_headers",
    "build_outbound_request_headers",
    "merge_outbound_headers",
    "PLUGIN_MODULE_PREFIX",
    "ParameterDefinition",
    "PluginConfigurationError",
    "PluginPathResolver",
    "PluginHardwareRuntimeProtocol",
    "PluginRuntimeServices",
    "PluginStorageReservationLeaseProtocol",
    "PluginStorageRuntimeProtocol",
    "PluginStorageWriteClaimProtocol",
    "ProviderStatusUpdatedEvent",
    "RemoteModelSearchError",
    "RemoteModelSearchResult",
    "RemoteModelSearchVariant",
    "build_model_search_terms",
    "hf_model_search",
    "resolve_hf_token",
    "normalize_model_search_payload",
    "RequestContext",
    "Shutdownable",
    "UNLOAD_ALL_MODELS_SENTINEL",
    "build_invalid_tool_call_json_error_details",
    "is_invalid_tool_call_json_contract_error",
    "validate_local_only_url",
    "validate_runtime_host_port",
    "async_safe_tar_zst_extractall",
    "async_isdir",
    "async_isfile",
    "async_islink",
    "async_listdir",
    "async_makedirs",
    "async_path_exists",
    "async_remove",
    "async_safe_tar_extractall",
    "async_safe_zip_extractall",
    "async_stream_download_to_file",
    "build_config",
    "build_auto_backend_variant_option",
    "LocalArtifact",
    "RemoteArtifact",
    "RemoteArtifactFile",
    "build_artifact_directory_name",
    "build_direct_artifact_directory",
    "collect_artifact_directories",
    "group_remote_artifact_files",
    "inspect_artifact_directory",
    "parse_artifact_shard_filename",
    "build_model_variant",
    "build_parameter_schema",
    "build_schema_cli_arguments",
    "build_accelerator_environment",
    "AcceleratorInventoryProviderProtocol",
    "snapshot_accelerator_inventory",
    "build_repository_artifact_directory",
    "build_repository_artifact_model_identifier",
    "resolve_repository_artifact_model_identifier",
    "calculate_directory_hash",
    "calculate_eta",
    "calculate_file_hash",
    "calculate_file_hash_sync",
    "enforce_offline_policy",
    "ensure_dirs_exist",
    "ensure_parent_dirs_exist",
    "error_type_to_status_code",
    "extract_quantization_token",
    "format_eta",
    "format_speed",
    "format_transfer_details",
    "format_transfer_log_suffix",
    "format_transfer_size",
    "format_transfer_status_message",
    "get_core_version",
    "get_runtime_platform",
    "get_path_size",
    "get_config_bool",
    "get_config_float",
    "get_config_int",
    "get_config_str",
    "guard_outbound_http_request",
    "is_block_private_network_egress_enabled",
    "is_loopback_host",
    "is_offline_mode_enabled",
    "merge_embedding_batch_responses",
    "normalize_hf_model_input",
    "normalize_backend_variant_id",
    "resolve_cuda_backend_availability",
    "normalize_variant_name",
    "prepare_embedding_batches",
    "read_metadata",
    "read_recent_process_log",
    "classify_memory_exhaustion",
    "raise_for_memory_exhaustion",
    "require_online_mode",
    "require_backend_variant_id",
    "resolve_model_download_required_bytes",
    "resolve_embedding_batch_limit",
    "run_periodic_task",
    "run_argv_capture",
    "build_minimal_subprocess_env",
    "runtime_flags",
    "safe_config_float",
    "safe_config_int",
    "resolve_plugin_backend_root",
    "safe_join_under_base",
    "ManagedProcessSession",
    "LoopbackListenerIdentity",
    "LoopbackListenerResolution",
    "resolve_verified_loopback_listener_identity",
    "spawn_logged_process",
    "terminate_verified_loopback_listener",
    "terminate_logged_process",
    "write_metadata_with_disk_reservation",
    "write_text_with_disk_reservation",
    "write_text_with_disk_reservation_sync",
    "SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER",
    "normalize_openai_messages_for_chat_template_role_policy",
    "normalize_openai_responses_input_for_chat_template_role_policy",
    "prepare_openai_request_for_chat_template_role_policy",
    "strip_soai_internal_chat_template_parameters",
    "build_openai_upstream_request_body_payload",
    "resolve_openai_upstream_custom_request_field_names",
)
