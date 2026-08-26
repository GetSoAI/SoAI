"""SoAI - System prompts catalog migration registry [backend/core/prompts/migrations/registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.migrations.payloads import PayloadMigrationStep

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("SYSTEM_PROMPTS_MIGRATION_STEPS",)


SYSTEM_PROMPTS_MIGRATION_STEPS: tuple[PayloadMigrationStep[JSONValue], ...] = ()
