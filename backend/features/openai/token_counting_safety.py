"""SoAI - Approximate prompt-token safety policy [backend/features/openai/token_counting_safety.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from core.config.strict_requirements import require_config_unit_interval_ratio

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.openai.token_accounting import PromptOccupancy

__all__ = (
    "resolve_approximate_prompt_reservation_tokens",
    "resolve_approximate_tokenizer_safety_ratio",
)

APPROXIMATE_TOKENIZER_SAFETY_RATIO_CONFIG_KEY = "API.OPENAI.TOKEN_COUNTING.APPROXIMATE_SAFETY_RATIO"


def resolve_approximate_tokenizer_safety_ratio(config: ConfigProtocol) -> float:
    return require_config_unit_interval_ratio(
        config,
        key=APPROXIMATE_TOKENIZER_SAFETY_RATIO_CONFIG_KEY,
        error_message=f"{APPROXIMATE_TOKENIZER_SAFETY_RATIO_CONFIG_KEY} must be > 0 and < 1.",
    )


def resolve_approximate_prompt_reservation_tokens(
    occupancy: PromptOccupancy,
    config: ConfigProtocol,
) -> int:
    if occupancy.precision == "exact":
        return occupancy.prompt_tokens
    ratio = resolve_approximate_tokenizer_safety_ratio(config)
    return math.ceil(occupancy.prompt_tokens / ratio)
