"""SoAI - Hugging Face type serialization [backend/plugin_sdk/hf/serialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.models.remote_model_search_payloads import (
    serialize_search_result,
    serialize_search_variant,
)

__all__ = ("serialize_search_result", "serialize_search_variant")
