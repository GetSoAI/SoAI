"""SoAI - Plugin SDK outbound HTTP header profiles [backend/plugin_sdk/contracts/outbound_headers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.network.outbound_http_profiles import (
    build_artifact_download_headers,
    build_github_api_headers,
    build_model_registry_headers,
    build_outbound_request_headers,
    merge_outbound_headers,
)

__all__ = (
    "build_artifact_download_headers",
    "build_github_api_headers",
    "build_model_registry_headers",
    "build_outbound_request_headers",
    "merge_outbound_headers",
)
