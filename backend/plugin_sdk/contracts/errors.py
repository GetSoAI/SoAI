"""SoAI - Plugin SDK error types [backend/plugin_sdk/contracts/errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.error_types import ErrorType
from core.errors.exceptions import ConfigurationError
from core.errors.status_mapping import error_type_to_status_code

__all__ = (
    "ErrorType",
    "PluginConfigurationError",
    "error_type_to_status_code",
)


class PluginConfigurationError(ConfigurationError): ...
