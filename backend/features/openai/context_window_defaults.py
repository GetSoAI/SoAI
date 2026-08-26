"""SoAI - OpenAI context window default resolution [backend/features/openai/context_window_defaults.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.integer_requirements import require_config_int_at_least

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol

__all__ = ("resolve_default_openai_context_window_tokens",)

DEFAULT_CONTEXT_WINDOW_CONFIG_KEY = "API.OPENAI.AGENTIC.DEFAULT_CONTEXT_WINDOW_TOKENS"


def resolve_default_openai_context_window_tokens(config: ConfigProtocol) -> int:
    return require_config_int_at_least(
        config.get_int(DEFAULT_CONTEXT_WINDOW_CONFIG_KEY),
        key=DEFAULT_CONTEXT_WINDOW_CONFIG_KEY,
        minimum=1,
    )
