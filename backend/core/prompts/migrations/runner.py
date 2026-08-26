"""SoAI - System prompts catalog migration runner [backend/core/prompts/migrations/runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.migrations.payloads import upgrade_mapping_payload_to_current
from core.prompts.migrations.registry import SYSTEM_PROMPTS_MIGRATION_STEPS

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict

__all__ = ("upgrade_system_prompts_payload_to_current",)

_MAX_MIGRATION_STEPS: int = 16


def upgrade_system_prompts_payload_to_current(
    payload: JSONDict,
    *,
    logger: LoggerProtocol,
) -> tuple[JSONDict, tuple[str, ...]]:
    return upgrade_mapping_payload_to_current(
        payload,
        steps=SYSTEM_PROMPTS_MIGRATION_STEPS,
        logger=logger,
        max_steps=_MAX_MIGRATION_STEPS,
        payload_label="System prompts payload",
        migration_label="System prompts",
        non_mapping_input_message="System prompts payload must be a JSON object.",
        non_mapping_output_message="returned a non-object payload.",
    )
