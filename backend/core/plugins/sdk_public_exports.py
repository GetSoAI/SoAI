"""SoAI - Public plugin SDK export policy data [backend/core/plugins/sdk_public_exports.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.plugins.sdk_public_all_exports import (
    NATIVE_COMPATIBILITY_ASSESSMENT_EXPORTS,
    NATIVE_COMPATIBILITY_EXPORTS,
    NATIVE_RUNTIME_PROBE_EXPORTS,
    OUTBOUND_HEADER_EXPORTS,
    PLUGIN_LOGO_EXPORTS,
    PUBLIC_PLUGIN_SDK_EXPORTS,
)
from core.plugins.sdk_public_openai_exports import (
    OPENAI_AUDIO_UPLOAD_RESPONSE_EXPORTS,
    OPENAI_EXPORTS,
    OPENAI_PROVIDER_TRANSPORT_EXPORTS,
)

__all__ = (
    "NATIVE_COMPATIBILITY_ASSESSMENT_EXPORTS",
    "CHAT_TEMPLATE_ROLE_POLICY_EXPORTS",
    "ERROR_EXPORTS",
    "HF_SEARCH_EXPORTS",
    "MODEL_ARTIFACT_EXPORTS",
    "NATIVE_COMPATIBILITY_EXPORTS",
    "NATIVE_RUNTIME_PROBE_EXPORTS",
    "OPENAI_AUDIO_UPLOAD_RESPONSE_EXPORTS",
    "OPENAI_EXPORTS",
    "OPENAI_PROVIDER_TRANSPORT_EXPORTS",
    "OUTBOUND_HEADER_EXPORTS",
    "PLUGIN_LOGO_EXPORTS",
    "PROCESS_SESSION_EXPORTS",
    "PROGRESS_EXPORTS",
    "PUBLIC_PLUGIN_SDK_EXPORTS",
    "REPOSITORY_ARTIFACT_EXPORTS",
    "RUNTIME_NETWORK_EXPORTS",
    "TRANSFER_FORMAT_EXPORTS",
)

RUNTIME_NETWORK_EXPORTS: tuple[str, ...] = (
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
)

PROGRESS_EXPORTS: tuple[str, ...] = (
    "get_progress_payload",
    "format_progress_bar",
    "SpeedCalculator",
    "ProgressPayload",
    "DownloadStatsPayload",
    "DownloadProgressReporter",
)
ERROR_EXPORTS: tuple[str, ...] = (
    "BackendPrerequisiteError",
    "AcceleratorMemoryExhaustedError",
    "ValidationError",
    "StateError",
    "SoAIError",
    "SecurityError",
    "ProcessError",
    "NotFoundError",
    "ModelOutputContractError",
    "FeatureDisabledError",
    "ExternalServiceError",
    "ConfigurationError",
    "SystemMemoryExhaustedError",
)
HF_SEARCH_EXPORTS: tuple[str, ...] = (
    "resolve_hf_token",
    "hf_model_search",
    "build_model_search_terms",
    "RemoteModelSearchVariant",
    "RemoteModelSearchResult",
    "RemoteModelSearchError",
)
MODEL_ARTIFACT_EXPORTS: tuple[str, ...] = (
    "parse_artifact_shard_filename",
    "inspect_artifact_directory",
    "group_remote_artifact_files",
    "collect_artifact_directories",
    "build_direct_artifact_directory",
    "build_artifact_directory_name",
    "RemoteArtifactFile",
    "RemoteArtifact",
    "LocalArtifact",
)
REPOSITORY_ARTIFACT_EXPORTS: tuple[str, ...] = (
    "resolve_repository_artifact_model_identifier",
    "build_repository_artifact_model_identifier",
    "build_repository_artifact_directory",
)
TRANSFER_FORMAT_EXPORTS: tuple[str, ...] = (
    "format_transfer_status_message",
    "format_transfer_size",
    "format_transfer_log_suffix",
    "format_transfer_details",
    "format_speed",
)
PROCESS_SESSION_EXPORTS: tuple[str, ...] = (
    "terminate_logged_process",
    "spawn_logged_process",
    "ManagedProcessSession",
)
CHAT_TEMPLATE_ROLE_POLICY_EXPORTS: tuple[str, ...] = (
    "strip_soai_internal_chat_template_parameters",
    "prepare_openai_request_for_chat_template_role_policy",
    "normalize_openai_responses_input_for_chat_template_role_policy",
    "normalize_openai_messages_for_chat_template_role_policy",
    "SOAI_CHAT_TEMPLATE_MAX_ROLE_PARAMETER",
)
