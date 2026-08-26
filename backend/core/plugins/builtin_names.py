"""SoAI - Built-in plugin names [backend/core/plugins/builtin_names.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("BUILTIN_PLUGIN_NAMES",)

BUILTIN_PLUGIN_NAMES: tuple[str, ...] = (
    "external",
    "llamacpp",
    "ollama",
    "vllm",
    "ctranslate2",
    "embedding",
    "melotts",
    "whisper",
)
