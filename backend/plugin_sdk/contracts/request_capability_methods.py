"""SoAI - Plugin SDK capability fallback method exports [backend/plugin_sdk/contracts/request_capability_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.plugins.request_capability_methods import (
    count_prompt_tokens_method,
    get_available_variants_method,
    handle_embedding_request_method,
    search_remote_models_method,
)

__all__ = (
    "count_prompt_tokens_method",
    "get_available_variants_method",
    "handle_embedding_request_method",
    "search_remote_models_method",
)
