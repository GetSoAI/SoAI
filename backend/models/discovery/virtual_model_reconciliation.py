"""SoAI - Virtual model reconciliation for model changes [backend/models/discovery/virtual_model_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.models.protocols_database import DatabaseModelsProtocol
from core.orchestrator.routing_config import VirtualModelConfig

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("reconcile_virtual_models_for_removed_universal_ids",)

LOGGER_NAME = "SoAI.models.discovery.virtual_model_reconciliation"


async def reconcile_virtual_models_for_removed_universal_ids(
    removed_universal_ids: list[str],
    database_models: DatabaseModelsProtocol,
    virtual_model_get: Callable[[str], Awaitable[VirtualModelConfig | None]],
    virtual_model_delete: Callable[[str], Awaitable[bool]],
    virtual_model_update: Callable[[str, JSONDict], Awaitable[VirtualModelConfig]],
) -> bool:
    logger = get_logger(LOGGER_NAME)
    if not removed_universal_ids:
        return False
    uid_to_virtual_models = await database_models.find_virtual_models_using_universal_ids(
        removed_universal_ids,
    )
    virtual_models_by_name: dict[str, set[str]] = defaultdict(set)
    for universal_id, virtual_model_names in uid_to_virtual_models.items():
        for virtual_model_name in virtual_model_names:
            virtual_models_by_name[virtual_model_name].add(universal_id)
    if not virtual_models_by_name:
        return False
    for virtual_model_name, model_universal_ids in virtual_models_by_name.items():
        virtual_model = await virtual_model_get(virtual_model_name)
        if virtual_model:
            original_count = len(virtual_model.models)
            virtual_model.models = [
                model_entry
                for model_entry in virtual_model.models
                if model_entry.universal_id not in model_universal_ids
            ]
            if len(virtual_model.models) <= 1:
                logger.critical(
                    "Virtual model '%s' has %s constituent(s) left (minimum is 2). Deleting it.",
                    virtual_model_name,
                    len(virtual_model.models),
                )
                await virtual_model_delete(virtual_model_name)
            elif len(virtual_model.models) < original_count:
                logger.warning(
                    "Removed %s stale model(s) from virtual model '%s'.",
                    original_count - len(virtual_model.models),
                    virtual_model_name,
                )
                await virtual_model_update(
                    virtual_model_name,
                    {"models": [asdict(model_entry) for model_entry in virtual_model.models]},
                )
    return True
