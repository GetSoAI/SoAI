"""SoAI - Config schema migration step registry [backend/core/config/migrations/registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.migrations.payloads import PayloadMigrationStep

if TYPE_CHECKING:
    from core.config.value_types import ConfigValue

__all__ = ("CONFIG_MIGRATION_STEPS",)


CONFIG_MIGRATION_STEPS: tuple[PayloadMigrationStep[ConfigValue], ...] = ()
