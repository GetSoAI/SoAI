"""SoAI - Plugin SDK runtime utilities and operating context resolution [backend/plugin_sdk/runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.lifecycle.protocols import Shutdownable
from core.models.model_context import ModelContext
from core.runtime.platform import RuntimePlatform, get_runtime_platform, runtime_flags
from core.runtime.request_context import RequestContext, create_system_context

__all__ = (
    "ModelContext",
    "RequestContext",
    "RuntimePlatform",
    "Shutdownable",
    "create_system_context",
    "get_runtime_platform",
    "runtime_flags",
)
