"""SoAI - Standardized error type contracts [backend/core/errors/error_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from enum import Enum

__all__ = ("ErrorType",)


class ErrorType(Enum):
    SERVER_ERROR = "server_error"
    TIMEOUT_ERROR = "timeout_error"
    INVALID_REQUEST = "invalid_request_error"
    AUTHENTICATION_ERROR = "authentication_error"
    FORBIDDEN = "forbidden_error"
    NOT_FOUND = "not_found_error"
    INFERENCE_ERROR = "inference_error"
    MODEL_OUTPUT_CONTRACT = "model_output_contract_error"
    MODEL_STOPPED = "model_stopped_error"
    MODEL_DELETED = "model_deleted_error"
    SERVICE_UNAVAILABLE = "service_unavailable"
    OVERLOADED = "overloaded_error"
    PLUGIN_UNAVAILABLE = "plugin_unavailable_error"
    PLUGIN_QUARANTINED = "plugin_quarantined_error"
    PLUGIN_DISABLED = "plugin_disabled_error"
    PLUGIN_INITIALIZING = "plugin_initializing_error"
    INVALID_STREAM = "invalid_stream_error"
    UPLOAD_ERROR = "upload_error"
    CONFLICT = "conflict_error"
    RATE_LIMIT = "rate_limit_error"
    LOCKED = "locked_error"
    ACTION_NOT_SUPPORTED = "action_not_supported"
    ACCELERATOR_MEMORY_EXHAUSTED = "accelerator_memory_exhausted"
    SYSTEM_MEMORY_EXHAUSTED = "system_memory_exhausted"
