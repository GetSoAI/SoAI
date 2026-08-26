"""SoAI - Agent compaction budget resolution [backend/features/agent/session/compaction_budget.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ConfigurationError, ValidationError
from core.validation.strings import coerce_optional_trimmed_str
from features.agent.session.compaction_config_values import (
    resolve_compaction_post_compact_margin_ratio,
    resolve_compaction_reserved_output_tokens,
    resolve_compaction_summary_max_tokens,
    resolve_compaction_trigger_margin_ratio,
)
from features.openai.context_window_defaults import (
    resolve_default_openai_context_window_tokens,
)
from features.openai.model_context_resolution import (
    resolve_context_window_tokens_for_request_model,
)
from features.openai.token_counting_safety import (
    resolve_approximate_tokenizer_safety_ratio,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.agent.settings_types import AgentSettings
    from core.config.protocols import ConfigProtocol
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelResolutionServiceProtocol,
    )
    from core.orchestrator.routing_config import VirtualModelConfig

__all__ = (
    "ResolvedCompactionBudget",
    "resolve_compaction_budget_for_request_model",
    "resolve_compaction_budget_from_agent_settings",
    "resolve_compaction_budget_from_context_window",
    "resolve_compaction_summary_prompt_budget_from_context_window",
)


@dataclass(frozen=True, slots=True)
class ResolvedCompactionBudget:
    context_window_tokens: int
    reserved_output_tokens: int
    trigger_margin_ratio: float
    post_compact_margin_ratio: float
    trigger_prompt_tokens: int
    target_prompt_tokens: int

    @property
    def maximum_prompt_tokens(self) -> int:
        return self.context_window_tokens - self.reserved_output_tokens


def resolve_compaction_budget_from_agent_settings(
    agent_settings: AgentSettings,
) -> ResolvedCompactionBudget | None:
    if (
        agent_settings.compaction_trigger_prompt_tokens is None
        and agent_settings.compaction_target_prompt_tokens is None
    ):
        return None
    if agent_settings.compaction_context_window_tokens is None:
        raise ValidationError("Agent settings require a fully resolved compaction budget.")
    if agent_settings.compaction_reserved_output_tokens is None:
        raise ValidationError("Agent settings require a fully resolved compaction budget.")
    if agent_settings.compaction_trigger_margin_ratio is None:
        raise ValidationError("Agent settings require a fully resolved compaction budget.")
    if agent_settings.compaction_post_compact_margin_ratio is None:
        raise ValidationError("Agent settings require a fully resolved compaction budget.")
    if agent_settings.compaction_trigger_prompt_tokens is None:
        raise ValidationError("Agent settings require a fully resolved compaction budget.")
    if agent_settings.compaction_target_prompt_tokens is None:
        raise ValidationError("Agent settings require a fully resolved compaction budget.")
    return ResolvedCompactionBudget(
        context_window_tokens=agent_settings.compaction_context_window_tokens,
        reserved_output_tokens=agent_settings.compaction_reserved_output_tokens,
        trigger_margin_ratio=agent_settings.compaction_trigger_margin_ratio,
        post_compact_margin_ratio=agent_settings.compaction_post_compact_margin_ratio,
        trigger_prompt_tokens=agent_settings.compaction_trigger_prompt_tokens,
        target_prompt_tokens=agent_settings.compaction_target_prompt_tokens,
    )


def resolve_compaction_budget_from_context_window(
    *,
    config: ConfigProtocol,
    context_window_tokens: int | None,
    tokenizer_is_approximate: bool = False,
) -> ResolvedCompactionBudget:
    if (
        context_window_tokens is None
        or isinstance(context_window_tokens, bool)
        or int(context_window_tokens) <= 0
    ):
        raise ValidationError("Compaction requires a resolved positive context window.")
    resolved_context_window_tokens = int(context_window_tokens)
    if tokenizer_is_approximate:
        safety_ratio = resolve_approximate_tokenizer_safety_ratio(config)
        resolved_context_window_tokens = max(
            1,
            math.floor(resolved_context_window_tokens * safety_ratio),
        )
    reserved_output_tokens = resolve_compaction_reserved_output_tokens(config)
    effective_context_window = resolved_context_window_tokens - reserved_output_tokens
    if effective_context_window < 1:
        message = "".join(
            (
                "Compaction requires an effective context window after output reservation ",
                f"(context_window_tokens={resolved_context_window_tokens}, ",
                f"reserved_output_tokens={reserved_output_tokens}).",
            ),
        )
        raise ConfigurationError(
            message,
        )
    trigger_margin_ratio = resolve_compaction_trigger_margin_ratio(config)
    post_compact_margin_ratio = resolve_compaction_post_compact_margin_ratio(
        config=config,
        trigger_margin_ratio=trigger_margin_ratio,
    )
    trigger_prompt_tokens = math.floor(effective_context_window * (1.0 - trigger_margin_ratio))
    target_prompt_tokens = math.floor(effective_context_window * (1.0 - post_compact_margin_ratio))
    if trigger_prompt_tokens <= 0 or target_prompt_tokens <= 0:
        message = "".join(
            (
                "Compaction derived prompt budget must be positive ",
                f"(context_window_tokens={resolved_context_window_tokens}, ",
                f"reserved_output_tokens={reserved_output_tokens}, ",
                f"trigger_margin_ratio={trigger_margin_ratio}, ",
                f"post_compact_margin_ratio={post_compact_margin_ratio}, ",
                f"trigger_prompt_tokens={trigger_prompt_tokens}, ",
                f"target_prompt_tokens={target_prompt_tokens}).",
            ),
        )
        raise ConfigurationError(
            message,
        )
    if target_prompt_tokens >= trigger_prompt_tokens:
        message = "".join(
            (
                "Compaction hysteresis requires target_prompt_tokens < trigger_prompt_tokens ",
                f"(context_window_tokens={resolved_context_window_tokens}, ",
                f"reserved_output_tokens={reserved_output_tokens}, ",
                f"trigger_margin_ratio={trigger_margin_ratio}, ",
                f"post_compact_margin_ratio={post_compact_margin_ratio}, ",
                f"trigger_prompt_tokens={trigger_prompt_tokens}, ",
                f"target_prompt_tokens={target_prompt_tokens}).",
            ),
        )
        raise ConfigurationError(
            message,
        )
    return ResolvedCompactionBudget(
        context_window_tokens=resolved_context_window_tokens,
        reserved_output_tokens=reserved_output_tokens,
        trigger_margin_ratio=trigger_margin_ratio,
        post_compact_margin_ratio=post_compact_margin_ratio,
        trigger_prompt_tokens=trigger_prompt_tokens,
        target_prompt_tokens=target_prompt_tokens,
    )


def resolve_compaction_summary_prompt_budget_from_context_window(
    *,
    config: ConfigProtocol,
    context_window_tokens: int | None,
) -> int:
    if (
        context_window_tokens is None
        or isinstance(context_window_tokens, bool)
        or int(context_window_tokens) <= 0
    ):
        raise ValidationError("Compaction requires a resolved positive context window.")
    resolved_context_window_tokens = int(context_window_tokens)
    summary_max_tokens = resolve_compaction_summary_max_tokens(config)
    effective_context_window = resolved_context_window_tokens - int(summary_max_tokens)
    if effective_context_window < 1:
        message = "".join(
            (
                "Compaction summarizer requires an effective context window ",
                "after output reservation ",
                f"(context_window_tokens={resolved_context_window_tokens}, ",
                f"summary_max_tokens={summary_max_tokens}).",
            ),
        )
        raise ConfigurationError(
            message,
        )
    return int(effective_context_window)


async def resolve_compaction_budget_for_request_model(
    *,
    config: ConfigProtocol,
    model_name: str,
    model_resolution_service: ModelResolutionServiceProtocol,
    model_information_service: ModelInformationServiceProtocol,
    virtual_model_get: (
        Callable[[str], Awaitable[VirtualModelConfig | None] | VirtualModelConfig | None] | None
    ) = None,
) -> ResolvedCompactionBudget:
    normalized_model_name = coerce_optional_trimmed_str(model_name)
    if normalized_model_name is None:
        raise ValidationError("Compaction budget requires a resolved model.")
    context_window_tokens = await resolve_context_window_tokens_for_request_model(
        model_name=normalized_model_name,
        model_resolution_service=model_resolution_service,
        model_information_service=model_information_service,
        virtual_model_get=virtual_model_get,
    )
    if context_window_tokens is None:
        context_window_tokens = resolve_default_openai_context_window_tokens(config)
    return resolve_compaction_budget_from_context_window(
        config=config,
        context_window_tokens=context_window_tokens,
        tokenizer_is_approximate=True,
    )
