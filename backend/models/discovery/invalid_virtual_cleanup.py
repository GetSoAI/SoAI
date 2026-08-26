"""SoAI - Invalid virtual model cleanup for discovery startup [backend/models/discovery/invalid_virtual_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.logging.trace import get_logger
from core.models.protocols_database import DatabaseModelsProtocol

__all__ = ("cleanup_invalid_virtual_models",)

LOGGER_NAME = "SoAI.models.discovery.invalid_virtual_cleanup"


async def cleanup_invalid_virtual_models(
    database_models: DatabaseModelsProtocol,
    virtual_model_delete: Callable[[str], Awaitable[bool]],
) -> int:
    logger = get_logger(LOGGER_NAME)
    deleted_count = 0
    for virtual_model in await database_models.list_all_virtual_models():
        if len(virtual_model.models) <= 1:
            logger.critical(
                "Virtual model '%s' has %s constituent(s) (minimum is 2). Deleting it.",
                virtual_model.name,
                len(virtual_model.models),
            )
            if await virtual_model_delete(virtual_model.name):
                deleted_count += 1
    return deleted_count
