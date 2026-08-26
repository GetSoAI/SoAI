"""SoAI - Plugin SDK error exports [backend/plugin_sdk/errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import (
    AcceleratorMemoryExhaustedError,
    ConfigurationError,
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
from core.errors.external_service_exception import ExternalServiceError

__all__ = (
    "ConfigurationError",
    "AcceleratorMemoryExhaustedError",
    "ExternalServiceError",
    "FeatureDisabledError",
    "ModelOutputContractError",
    "NotFoundError",
    "ProcessError",
    "SecurityError",
    "SoAIError",
    "StateError",
    "SystemMemoryExhaustedError",
    "ValidationError",
)
