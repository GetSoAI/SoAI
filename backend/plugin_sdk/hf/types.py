"""SoAI - Plugin SDK Hugging Face model search types [backend/plugin_sdk/hf/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.models.remote_model_search_types import (
    HuggingFaceReference,
    RemoteModelSearchError,
    RemoteModelSearchResult,
    RemoteModelSearchVariant,
)

__all__ = (
    "HuggingFaceReference",
    "RemoteModelSearchError",
    "RemoteModelSearchResult",
    "RemoteModelSearchVariant",
)
