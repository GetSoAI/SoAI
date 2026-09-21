"""SoAI - Public plugin SDK export policy data [backend/core/plugins/sdk_public_exports.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.plugins.sdk_public_all_exports import (
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
    "ASYNC_FILESYSTEM_EXPORTS",
    "CHAT_TEMPLATE_ROLE_POLICY_EXPORTS",
    "ERROR_EXPORTS",
    "HF_SEARCH_EXPORTS",
    "MODEL_ARTIFACT_EXPORTS",
    "OPENAI_AUDIO_UPLOAD_RESPONSE_EXPORTS",
    "OPENAI_EXPORTS",
    "OPENAI_PROVIDER_TRANSPORT_EXPORTS",
    "OUTBOUND_HEADER_EXPORTS",
    "PLUGIN_LOGO_EXPORTS",
    "PROCESS_SESSION_EXPORTS",
    "PROGRESS_EXPORTS",
    "PUBLIC_PLUGIN_SDK_EXPORTS",
    "REPOSITORY_ARTIFACT_EXPORTS",
    "TRANSFER_FORMAT_EXPORTS",
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
ASYNC_FILESYSTEM_EXPORTS: tuple[str, ...] = (
    "async_remove",
    "async_path_exists",
    "async_makedirs",
    "async_listdir",
    "async_islink",
    "async_isfile",
    "async_isdir",
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
