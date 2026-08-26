"""SoAI - Media preview cache metadata migration registry [backend/webui/manager/media_preview_cache_metadata_registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.migrations.payloads import PayloadMigrationStep

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("MEDIA_PREVIEW_CACHE_METADATA_MIGRATION_STEPS",)


MEDIA_PREVIEW_CACHE_METADATA_MIGRATION_STEPS: tuple[PayloadMigrationStep[JSONValue], ...] = ()
