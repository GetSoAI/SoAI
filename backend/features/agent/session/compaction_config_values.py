"""SoAI - Agent compaction configuration value resolution [backend/features/agent/session/compaction_config_values.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.strict_requirements import (
    require_config_non_negative_int,
    require_config_unit_interval_ratio,
)
from core.errors.exceptions import ConfigurationError

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol

__all__ = (
    "resolve_compaction_post_compact_margin_ratio",
    "resolve_compaction_reserved_output_tokens",
    "resolve_compaction_summary_max_tokens",
    "resolve_compaction_trigger_margin_ratio",
)

COMPACTION_TRIGGER_MARGIN_RATIO_CONFIG_KEY = "API.OPENAI.AGENTIC.COMPACTION.CONTEXT_MARGIN_RATIO"
COMPACTION_POST_COMPACT_MARGIN_RATIO_CONFIG_KEY = (
    "API.OPENAI.AGENTIC.COMPACTION.POST_COMPACT_MARGIN_RATIO"
)
COMPACTION_RESERVED_OUTPUT_TOKENS_CONFIG_KEY = (
    "API.OPENAI.AGENTIC.COMPACTION.RESERVED_OUTPUT_TOKENS"
)
COMPACTION_SUMMARY_MAX_TOKENS_CONFIG_KEY = "API.OPENAI.AGENTIC.COMPACTION.SUMMARY_MAX_TOKENS"


def resolve_compaction_trigger_margin_ratio(config: ConfigProtocol) -> float:
    return require_config_unit_interval_ratio(
        config,
        key=COMPACTION_TRIGGER_MARGIN_RATIO_CONFIG_KEY,
        error_message=f"{COMPACTION_TRIGGER_MARGIN_RATIO_CONFIG_KEY} must be > 0 and < 1.",
    )


def resolve_compaction_post_compact_margin_ratio(
    *,
    config: ConfigProtocol,
    trigger_margin_ratio: float,
) -> float:
    ratio = require_config_unit_interval_ratio(
        config,
        key=COMPACTION_POST_COMPACT_MARGIN_RATIO_CONFIG_KEY,
        error_message=f"{COMPACTION_POST_COMPACT_MARGIN_RATIO_CONFIG_KEY} must be > 0 and < 1.",
    )
    if ratio <= trigger_margin_ratio:
        message = "".join(
            (
                f"{COMPACTION_POST_COMPACT_MARGIN_RATIO_CONFIG_KEY} must be greater than ",
                f"{COMPACTION_TRIGGER_MARGIN_RATIO_CONFIG_KEY}.",
            ),
        )
        raise ConfigurationError(
            message,
        )
    return ratio


def resolve_compaction_reserved_output_tokens(config: ConfigProtocol) -> int:
    return require_config_non_negative_int(
        config,
        key=COMPACTION_RESERVED_OUTPUT_TOKENS_CONFIG_KEY,
        error_message=f"{COMPACTION_RESERVED_OUTPUT_TOKENS_CONFIG_KEY} must be a non-negative integer.",
    )


def resolve_compaction_summary_max_tokens(config: ConfigProtocol) -> int:
    return require_config_non_negative_int(
        config,
        key=COMPACTION_SUMMARY_MAX_TOKENS_CONFIG_KEY,
        error_message=f"{COMPACTION_SUMMARY_MAX_TOKENS_CONFIG_KEY} must be a non-negative integer.",
    )
