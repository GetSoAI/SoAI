"""SoAI - Agent session settings resolver [backend/features/agent/session/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.iteration_limits import resolve_agent_max_iterations
from core.agent.settings_types import AgentSettings
from core.agent_mode import normalize_agent_mode
from core.config.byte_sizes import mib_to_bytes
from core.config.integer_requirements import (
    require_config_int_at_least,
    require_config_int_between,
)
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.files.protocols import FilesPathResolverProtocol
from core.model_settings.normalization import read_optional_agent_settings
from core.openai.token_estimation_profile import TokenEstimationProfile
from core.workspaces.conversation_workspace_path import (
    read_conversation_workspace_path_override,
    resolve_effective_conversation_workspace_path,
)
from features.agent.session.compaction_budget import (
    resolve_compaction_budget_from_context_window,
)
from features.api.runtime.preview_contract_retry_settings import (
    resolve_preview_contract_max_retries,
)
from features.openai.context_window_defaults import (
    resolve_default_openai_context_window_tokens,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("resolve_agent_settings",)


def resolve_agent_settings(
    *,
    config: ConfigProtocol,
    files: FilesPathResolverProtocol,
    user_workspace_path: str,
    model_settings: JSONDict,
    context_window_tokens: int | None = None,
    context_window_unverified: bool = False,
    token_estimation_profile: TokenEstimationProfile | None = None,
    tool_result_image_relay_enabled: bool = False,
) -> AgentSettings:
    agent_config = read_optional_agent_settings(model_settings)
    mode = normalize_agent_mode(agent_config.get("mode"), strict=True)
    max_iterations = resolve_agent_max_iterations(agent_config)

    empty_output_max_retries = require_config_int_at_least(
        config.get_int("API.OPENAI.AGENTIC.EMPTY_OUTPUT_MAX_RETRIES"),
        key="API.OPENAI.AGENTIC.EMPTY_OUTPUT_MAX_RETRIES",
        minimum=0,
    )

    empty_output_silent_max_retries = require_config_int_at_least(
        config.get_int("API.OPENAI.AGENTIC.EMPTY_OUTPUT_SILENT_MAX_RETRIES"),
        key="API.OPENAI.AGENTIC.EMPTY_OUTPUT_SILENT_MAX_RETRIES",
        minimum=0,
    )

    max_output_tokens = require_config_int_at_least(
        config.get_int("API.OPENAI.AGENTIC.MAX_OUTPUT_TOKENS"),
        key="API.OPENAI.AGENTIC.MAX_OUTPUT_TOKENS",
        minimum=1,
    )

    if "compaction_max_prompt_tokens" in agent_config:
        raise ValidationError(
            "model_settings.agent.compaction_max_prompt_tokens is no longer supported.",
        )
    resolved_context_window_tokens = context_window_tokens
    resolved_context_window_unverified = context_window_unverified
    if resolved_context_window_tokens is None:
        resolved_context_window_tokens = resolve_default_openai_context_window_tokens(config)
        resolved_context_window_unverified = True
    resolved_token_estimation_profile = (
        token_estimation_profile
        if token_estimation_profile is not None
        else TokenEstimationProfile.exact("cl100k_base")
    )
    compaction_budget = resolve_compaction_budget_from_context_window(
        config=config,
        context_window_tokens=resolved_context_window_tokens,
        tokenizer_is_approximate=resolved_token_estimation_profile.is_approximate,
    )

    effective_workspace_path = resolve_effective_conversation_workspace_path(
        files=files,
        user_workspace_path=user_workspace_path,
        override_workspace_path=read_conversation_workspace_path_override(model_settings),
        require_existing_directories=True,
    )

    tool_result_prompt_max_chars = require_config_int_between(
        config.get_int("API.OPENAI.AGENTIC.TOOL_RESULT_PROMPT_MAX_CHARS"),
        key="API.OPENAI.AGENTIC.TOOL_RESULT_PROMPT_MAX_CHARS",
        minimum=1000,
        maximum=500_000,
    )

    tool_result_prompt_max_total_chars_per_tool_block = require_config_int_between(
        config.get_int("API.OPENAI.AGENTIC.TOOL_RESULT_PROMPT_MAX_TOTAL_CHARS_PER_TOOL_BLOCK"),
        key="API.OPENAI.AGENTIC.TOOL_RESULT_PROMPT_MAX_TOTAL_CHARS_PER_TOOL_BLOCK",
        minimum=1000,
        maximum=2_000_000,
    )

    tool_result_prompt_max_depth = require_config_int_between(
        config.get_int("API.OPENAI.AGENTIC.TOOL_RESULT_PROMPT_MAX_DEPTH"),
        key="API.OPENAI.AGENTIC.TOOL_RESULT_PROMPT_MAX_DEPTH",
        minimum=1,
        maximum=50,
    )

    tool_result_prompt_max_items = require_config_int_between(
        config.get_int("API.OPENAI.AGENTIC.TOOL_RESULT_PROMPT_MAX_ITEMS"),
        key="API.OPENAI.AGENTIC.TOOL_RESULT_PROMPT_MAX_ITEMS",
        minimum=10,
        maximum=10_000,
    )

    tool_result_prompt_max_keys = require_config_int_between(
        config.get_int("API.OPENAI.AGENTIC.TOOL_RESULT_PROMPT_MAX_KEYS"),
        key="API.OPENAI.AGENTIC.TOOL_RESULT_PROMPT_MAX_KEYS",
        minimum=10,
        maximum=10_000,
    )
    tool_result_image_relay_max_encoded_chars = require_config_int_between(
        config.get_int("API.OPENAI.AGENTIC.TOOL_RESULT_IMAGE_RELAY_MAX_ENCODED_CHARS"),
        key="API.OPENAI.AGENTIC.TOOL_RESULT_IMAGE_RELAY_MAX_ENCODED_CHARS",
        minimum=1024,
        maximum=mib_to_bytes(128),
    )

    tool_result_image_relay_max_pixels = require_config_int_between(
        config.get_int("API.OPENAI.AGENTIC.TOOL_RESULT_IMAGE_RELAY_MAX_PIXELS"),
        key="API.OPENAI.AGENTIC.TOOL_RESULT_IMAGE_RELAY_MAX_PIXELS",
        minimum=1,
        maximum=128_000_000,
    )
    preview_contract_max_retries = resolve_preview_contract_max_retries(config)
    return AgentSettings(
        mode=mode,
        max_iterations=max_iterations,
        max_output_tokens=max_output_tokens,
        compaction_trigger_prompt_tokens=compaction_budget.trigger_prompt_tokens,
        compaction_target_prompt_tokens=compaction_budget.target_prompt_tokens,
        workspace_path=effective_workspace_path,
        compaction_context_window_tokens=compaction_budget.context_window_tokens,
        token_estimation_profile=resolved_token_estimation_profile,
        context_window_unverified=resolved_context_window_unverified,
        compaction_trigger_margin_ratio=compaction_budget.trigger_margin_ratio,
        compaction_post_compact_margin_ratio=compaction_budget.post_compact_margin_ratio,
        compaction_reserved_output_tokens=compaction_budget.reserved_output_tokens,
        tool_result_image_relay_enabled=tool_result_image_relay_enabled,
        tool_result_image_relay_max_encoded_chars=tool_result_image_relay_max_encoded_chars,
        tool_result_image_relay_max_pixels=tool_result_image_relay_max_pixels,
        tool_result_prompt_max_chars=tool_result_prompt_max_chars,
        tool_result_prompt_max_total_chars_per_tool_block=(
            tool_result_prompt_max_total_chars_per_tool_block
        ),
        tool_result_prompt_max_depth=tool_result_prompt_max_depth,
        tool_result_prompt_max_items=tool_result_prompt_max_items,
        tool_result_prompt_max_keys=tool_result_prompt_max_keys,
        empty_output_max_retries=empty_output_max_retries,
        empty_output_silent_max_retries=empty_output_silent_max_retries,
        preview_contract_max_retries=preview_contract_max_retries,
    )
