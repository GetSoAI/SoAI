"""SoAI - Agent settings types [backend/core/agent/settings_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from core.config.byte_sizes import mib_to_bytes
from core.openai.token_estimation_profile import TokenEstimationProfile
from core.tool_calls.tool_result_prompt_settings import (
    DEFAULT_TOOL_RESULT_PROMPT_MAX_CHARS,
    DEFAULT_TOOL_RESULT_PROMPT_MAX_DEPTH,
    DEFAULT_TOOL_RESULT_PROMPT_MAX_ITEMS,
    DEFAULT_TOOL_RESULT_PROMPT_MAX_KEYS,
    DEFAULT_TOOL_RESULT_PROMPT_MAX_TOTAL_CHARS_PER_TOOL_BLOCK,
)

if TYPE_CHECKING:
    AgentMode = Literal["chat", "plan", "execute"]
else:
    AgentMode = str

__all__ = ("AgentSettings",)


@dataclass(frozen=True, slots=True)
class AgentSettings:
    mode: AgentMode
    max_iterations: int
    compaction_trigger_prompt_tokens: int | None
    compaction_target_prompt_tokens: int | None
    workspace_path: str
    max_output_tokens: int = 32768
    token_estimation_profile: TokenEstimationProfile = field(
        default_factory=lambda: TokenEstimationProfile.exact("cl100k_base"),
    )
    context_window_unverified: bool = False
    compaction_context_window_tokens: int | None = None
    compaction_trigger_margin_ratio: float | None = None
    compaction_post_compact_margin_ratio: float | None = None
    compaction_reserved_output_tokens: int | None = None
    tool_result_image_relay_enabled: bool = False
    tool_result_image_relay_max_encoded_chars: int = mib_to_bytes(128)
    tool_result_image_relay_max_pixels: int = 4_000_000
    tool_result_prompt_max_chars: int = DEFAULT_TOOL_RESULT_PROMPT_MAX_CHARS
    tool_result_prompt_max_total_chars_per_tool_block: int = (
        DEFAULT_TOOL_RESULT_PROMPT_MAX_TOTAL_CHARS_PER_TOOL_BLOCK
    )
    tool_result_prompt_max_depth: int = DEFAULT_TOOL_RESULT_PROMPT_MAX_DEPTH
    tool_result_prompt_max_items: int = DEFAULT_TOOL_RESULT_PROMPT_MAX_ITEMS
    tool_result_prompt_max_keys: int = DEFAULT_TOOL_RESULT_PROMPT_MAX_KEYS
    empty_output_max_retries: int = 3
    empty_output_silent_max_retries: int = 2
    preview_contract_max_retries: int = 2
    inference_admission_max_retries: int = 5
