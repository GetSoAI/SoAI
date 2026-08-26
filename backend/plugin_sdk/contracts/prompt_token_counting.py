"""SoAI - Plugin SDK prompt token count contracts [backend/plugin_sdk/contracts/prompt_token_counting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.plugins.prompt_token_counting import (
    build_estimated_prompt_token_count_result,
    build_exact_prompt_token_count_result,
    build_unsupported_prompt_token_count_result,
)

__all__ = (
    "build_exact_prompt_token_count_result",
    "build_estimated_prompt_token_count_result",
    "build_unsupported_prompt_token_count_result",
)
