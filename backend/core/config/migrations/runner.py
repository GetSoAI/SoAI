"""SoAI - Config schema migration runner [backend/core/config/migrations/runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.migrations.registry import CONFIG_MIGRATION_STEPS
from core.migrations.payloads import upgrade_mapping_payload_to_current

if TYPE_CHECKING:
    from core.config.value_types import ConfigValue
    from core.logging.protocols import LoggerProtocol

    type ConfigDict = dict[str, ConfigValue]

__all__ = ("upgrade_config_payload_to_current",)

_MAX_MIGRATION_STEPS: int = 32


def upgrade_config_payload_to_current(
    payload: ConfigDict,
    *,
    logger: LoggerProtocol,
) -> tuple[ConfigDict, tuple[str, ...]]:
    return upgrade_mapping_payload_to_current(
        payload,
        steps=CONFIG_MIGRATION_STEPS,
        logger=logger,
        max_steps=_MAX_MIGRATION_STEPS,
        payload_label="Config payload",
        migration_label="Config",
        non_mapping_input_message="Config payload must be a mapping.",
        non_mapping_output_message="returned a non-mapping payload.",
    )
