"""SoAI - Media preview cache metadata migration runner [backend/webui/manager/media_preview_cache_metadata_runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.migrations.payloads import upgrade_mapping_payload_to_current
from webui.manager.media_preview_cache_metadata_registry import (
    MEDIA_PREVIEW_CACHE_METADATA_MIGRATION_STEPS,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict

__all__ = ("upgrade_media_preview_cache_metadata_payload_to_current",)

_MAX_MIGRATION_STEPS: int = 8


def upgrade_media_preview_cache_metadata_payload_to_current(
    payload: JSONDict,
    *,
    logger: LoggerProtocol,
) -> tuple[JSONDict, tuple[str, ...]]:
    return upgrade_mapping_payload_to_current(
        payload,
        steps=MEDIA_PREVIEW_CACHE_METADATA_MIGRATION_STEPS,
        logger=logger,
        max_steps=_MAX_MIGRATION_STEPS,
        payload_label="Media preview cache metadata payload",
        migration_label="Media preview cache metadata",
        non_mapping_input_message="Media preview cache metadata payload must be a JSON object.",
        non_mapping_output_message="returned a non-object payload.",
    )
