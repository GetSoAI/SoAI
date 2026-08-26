"""SoAI - Model variant listing helpers [backend/plugins/manager/model_variants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.runtime.network_policy import require_online_mode
from core.state.state_names import ORCH_STATE_QUARANTINED
from plugins.manager.capability_support import supports_plugin_capability_from_instance
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("get_model_variants",)

LOGGER_NAME = "SoAI.plugins.manager.model_variants"
OPERATION = "plugin_manager.get_available_variants"


async def get_model_variants(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str,
    model_id: str,
) -> list[JSONDict]:
    logger = get_logger(LOGGER_NAME)
    await self.require_ready()
    require_online_mode(
        self.dependencies.infrastructure.runtime_flags,
        source="model variant discovery",
    )
    canonical_name = self.normalize_plugin_name(plugin_name) or plugin_name
    plugin_status = await self.dependencies.infrastructure.state_aggregator.get_plugin_status(
        canonical_name,
    )
    if plugin_status == ORCH_STATE_QUARANTINED:
        raise ValidationError(
            f"Cannot list model variants for '{plugin_name}' because it is quarantined. Please reset its circuit breaker.",
        )
    instance = await self.require_loaded_plugin(canonical_name, auto_load=True)
    if not supports_plugin_capability_from_instance(
        instance,
        "SUPPORTS_MODEL_VARIANT_DISCOVERY",
    ):
        logger.trace("Plugin '%s' does not support variant discovery.", plugin_name)
        return []
    try:
        variants = await instance.get_available_variants(model_id)
        if not isinstance(variants, list):
            raise ValidationError("Plugin returned a non-list object for variants.")
        return [item for item in variants if isinstance(item, dict) and "name" in item]
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=f"Plugin '{plugin_name}' failed during get_available_variants for model '{model_id}'",
            operation=OPERATION,
            details={"plugin": plugin_name, "model_id": model_id},
        )
        raise
