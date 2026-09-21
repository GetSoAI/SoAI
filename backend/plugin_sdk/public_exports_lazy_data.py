"""SoAI - Plugin SDK lazy import module map [backend/plugin_sdk/public_exports_lazy_data.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.plugins.sdk_public_exports import (
    CHAT_TEMPLATE_ROLE_POLICY_EXPORTS,
    ERROR_EXPORTS,
    HF_SEARCH_EXPORTS,
    MODEL_ARTIFACT_EXPORTS,
    OPENAI_AUDIO_UPLOAD_RESPONSE_EXPORTS,
    OPENAI_EXPORTS,
    OPENAI_PROVIDER_TRANSPORT_EXPORTS,
    OUTBOUND_HEADER_EXPORTS,
    PLUGIN_LOGO_EXPORTS,
    PROCESS_SESSION_EXPORTS,
    PROGRESS_EXPORTS,
    REPOSITORY_ARTIFACT_EXPORTS,
    TRANSFER_FORMAT_EXPORTS,
)

__all__ = ()

LAZY_IMPORT_MODULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "core.plugins.logo_contract",
        PLUGIN_LOGO_EXPORTS,
    ),
    ("core.plugins.logo_images", ("sanitize_plugin_logo",)),
    ("core.archives.errors", ("ArchiveLinkTargetNotFoundError",)),
    (
        "plugin_sdk.contracts.archive_extraction",
        ("async_safe_tar_extractall", "async_safe_zip_extractall"),
    ),
    ("core.config.protocols", ("ConfigProtocol",)),
    ("core.errors.exception_coercion", ("coerce_to_soai_error",)),
    (
        "core.errors.memory_exhaustion",
        ("classify_memory_exhaustion", "raise_for_memory_exhaustion"),
    ),
    (
        "core.errors.exception_logging",
        ("log_exception", "log_handled_exception"),
    ),
    ("core.events.protocols", ("EventBusProtocol",)),
    (
        "core.filesystem.async_queries",
        (
            "async_path_exists",
            "async_makedirs",
            "async_listdir",
            "async_islink",
            "async_isfile",
            "async_isdir",
        ),
    ),
    (
        "core.filesystem.hashing",
        ("calculate_directory_hash", "calculate_file_hash", "calculate_file_hash_sync"),
    ),
    ("core.files.locking", ("guarded_file_lock",)),
    ("core.filesystem.size_calculation", ("get_path_size",)),
    (
        "core.openai.embedding",
        (
            "merge_embedding_batch_responses",
            "prepare_embedding_batches",
            "resolve_embedding_batch_limit",
        ),
    ),
    ("core.models.remote_model_search_payloads", ("normalize_model_search_payload",)),
    ("core.system.commands", ("run_argv_capture",)),
    ("core.system.subprocess_env", ("build_minimal_subprocess_env",)),
    (
        "core.openai.model_output_contract_errors",
        (
            "build_invalid_tool_call_json_error_details",
            "is_invalid_tool_call_json_contract_error",
        ),
    ),
    (
        "core.openai.context_overflow_validation",
        (
            "build_context_overflow_validation_error",
            "extract_context_overflow_validation",
        ),
    ),
    (
        "core.openai.provider_transport",
        OPENAI_PROVIDER_TRANSPORT_EXPORTS,
    ),
    (
        "core.openai.audio_upload_responses",
        OPENAI_AUDIO_UPLOAD_RESPONSE_EXPORTS,
    ),
    ("core.plugins.protocols_instance", ("FilesProtocol",)),
    ("core.tasks.periodic", ("run_periodic_task",)),
    ("core.types.json", ("JSONDict", "JSONValue")),
    ("core.types.protocols", ("HttpClientProtocol",)),
    ("plugin_sdk.config", ("Config", "ConfigError")),
    (
        "plugin_sdk.config_building",
        ("build_config", "safe_config_float", "safe_config_int"),
    ),
    ("plugin_sdk.contracts.base_plugin", ("BasePlugin",)),
    (
        "plugin_sdk.contracts.backend_variants",
        (
            "AUTO_BACKEND_VARIANT_ID",
            "build_auto_backend_variant_option",
            "normalize_backend_variant_id",
            "resolve_cuda_backend_availability",
            "require_backend_variant_id",
        ),
    ),
    (
        "plugin_sdk.contracts.errors",
        ("ErrorType", "PluginConfigurationError", "error_type_to_status_code"),
    ),
    (
        "plugin_sdk.contracts.model_artifacts",
        MODEL_ARTIFACT_EXPORTS,
    ),
    (
        "plugin_sdk.contracts.repository_artifacts",
        REPOSITORY_ARTIFACT_EXPORTS,
    ),
    ("plugin_sdk.contracts.metadata", ("ModelMetadataStore", "read_metadata")),
    (
        "plugin_sdk.contracts.reserved_writes",
        (
            "write_metadata_with_disk_reservation",
            "write_text_with_disk_reservation",
            "write_text_with_disk_reservation_sync",
        ),
    ),
    (
        "plugin_sdk.contracts.model_variants",
        (
            "build_model_variant",
            "normalize_variant_name",
            "resolve_model_download_required_bytes",
        ),
    ),
    (
        "plugin_sdk.contracts.openai",
        OPENAI_EXPORTS,
    ),
    (
        "plugin_sdk.contracts.openai_request_payloads",
        (
            "OpenAIRequestBodyOperation",
            "build_openai_upstream_request_body_payload",
            "resolve_openai_upstream_custom_request_field_names",
        ),
    ),
    (
        "plugin_sdk.contracts.parameters",
        ("ClonableField", "NoDefault", "ParameterDefinition", "build_parameter_schema"),
    ),
    (
        "plugin_sdk.contracts.schema_cli_arguments",
        ("build_schema_cli_arguments",),
    ),
    (
        "plugin_sdk.contracts.process_diagnostics",
        ("read_recent_process_log",),
    ),
    (
        "plugin_sdk.contracts.process_lifecycle",
        ("check_process_alive",),
    ),
    (
        "plugin_sdk.contracts.process_sessions",
        PROCESS_SESSION_EXPORTS,
    ),
    (
        "plugin_sdk.contracts.loopback_listener_processes",
        (
            "LoopbackListenerIdentity",
            "LoopbackListenerResolution",
            "resolve_verified_loopback_listener_identity",
            "terminate_verified_loopback_listener",
        ),
    ),
    (
        "plugin_sdk.contracts.config_access",
        ("get_config_bool", "get_config_float", "get_config_int", "get_config_str"),
    ),
    (
        "plugin_sdk.contracts.accelerator_environment",
        ("build_accelerator_environment",),
    ),
    ("plugin_sdk.protocols", ("AcceleratorInventoryProviderProtocol",)),
    ("plugin_sdk.contracts.accelerator_inventory", ("snapshot_accelerator_inventory",)),
    ("plugin_sdk.contracts.quantization_tokens", ("extract_quantization_token",)),
    (
        "plugin_sdk.contracts.prompt_token_counting",
        (
            "build_exact_prompt_token_count_result",
            "build_estimated_prompt_token_count_result",
            "build_unsupported_prompt_token_count_result",
        ),
    ),
    (
        "plugin_sdk.contracts.safe_paths",
        ("resolve_plugin_backend_root", "safe_join_under_base"),
    ),
    ("plugin_sdk.contracts.tar_zst_extraction", ("async_safe_tar_zst_extractall",)),
    ("plugin_sdk.contracts.downloads", ("async_stream_download_to_file",)),
    (
        "plugin_sdk.contracts.outbound_headers",
        OUTBOUND_HEADER_EXPORTS,
    ),
    (
        "plugin_sdk.contracts.progress",
        PROGRESS_EXPORTS,
    ),
    (
        "core.plugins.protocols_runtime",
        (
            "PluginStorageReservationLeaseProtocol",
            "PluginHardwareRuntimeProtocol",
            "PluginRuntimeFailureReporterProtocol",
            "PluginStorageRuntimeProtocol",
            "PluginStorageWriteClaimProtocol",
        ),
    ),
    (
        "core.plugins.runtime_services",
        (
            "PLUGIN_MODULE_PREFIX",
            "UNLOAD_ALL_MODELS_SENTINEL",
            "PluginPathResolver",
            "PluginRuntimeServices",
        ),
    ),
    (
        "plugin_sdk.contracts.transfer",
        (
            "calculate_eta",
            "format_eta",
            *TRANSFER_FORMAT_EXPORTS,
        ),
    ),
    ("plugin_sdk.contracts.version", ("get_core_version",)),
    (
        "plugin_sdk.errors",
        ERROR_EXPORTS,
    ),
    ("plugin_sdk.events", ("ProviderStatusUpdatedEvent",)),
    (
        "plugin_sdk.filesystem.directory_creation",
        ("ensure_dirs_exist", "ensure_parent_dirs_exist"),
    ),
    ("plugin_sdk.filesystem.files", ("Files",)),
    ("plugin_sdk.filesystem.removal", ("async_remove",)),
    ("plugin_sdk.hf.normalize", ("normalize_hf_model_input",)),
    (
        "plugin_sdk.hf.search",
        HF_SEARCH_EXPORTS,
    ),
    (
        "plugin_sdk.runtime",
        (
            "ModelContext",
            "RequestContext",
            "Shutdownable",
            "create_system_context",
            "get_runtime_platform",
            "runtime_flags",
        ),
    ),
    (
        "plugin_sdk.runtime_network",
        (
            "OfflineModeError",
            "create_guarded_async_http_client",
            "enforce_offline_policy",
            "guard_outbound_http_request",
            "is_block_private_network_egress_enabled",
            "is_loopback_host",
            "is_offline_mode_enabled",
            "require_online_mode",
            "validate_local_only_url",
            "validate_runtime_host_port",
        ),
    ),
    (
        "plugin_sdk.contracts.chat_template_role_policy",
        CHAT_TEMPLATE_ROLE_POLICY_EXPORTS,
    ),
)
