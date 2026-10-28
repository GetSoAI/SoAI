"""SoAI - Current backend variant compatibility observations [backend/plugins/manager/backend_variant_compatibility.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.plugins.backend_variant_compatibility import assess_backend_variant_options
from core.serialization.json import normalize_for_json
from core.types.dict import freeze_json_dict
from core.types.json import JSONDict
from core.types.json_value import coerce_json_dict
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol

if TYPE_CHECKING:
    from core.types.dict import FrozenJsonDict

__all__ = ("load_backend_variant_compatibility", "snapshot_backend_compatibility_observations")

OPERATION_OBSERVE_COMPATIBILITY = "plugins.observe_backend_variant_compatibility"
OBSERVATION_EXCEPTIONS: tuple[type[Exception], ...] = (*RECOVERABLE_EXCEPTIONS, OSError)


async def load_backend_variant_compatibility(
    manager: PluginManagerRuntimeProtocol, plugin_name: str, options: list[JSONDict]
) -> list[JSONDict]:
    if not any(isinstance(option.get("compatibility_requirements"), dict) for option in options):
        return options
    loaded = await manager.dependencies.infrastructure.config_manager.load_config(
        plugin_name, force_reload=True
    )
    configuration = coerce_json_dict(normalize_for_json(loaded)) if loaded is not None else {}
    if configuration is None:
        raise ValidationError("Backend compatibility configuration must be a JSON object.")
    frozen_configuration = freeze_json_dict(configuration)
    capabilities, inventory = await snapshot_backend_compatibility_observations(
        manager, plugin_name
    )
    return assess_backend_variant_options(
        options, capabilities=capabilities, configuration=frozen_configuration, inventory=inventory
    )


async def snapshot_backend_compatibility_observations(
    manager: PluginManagerRuntimeProtocol, plugin_name: str
) -> tuple[FrozenJsonDict, FrozenJsonDict | None]:
    hardware = manager.dependencies.infrastructure.hw_manager
    capabilities = freeze_json_dict({})
    try:
        capabilities = freeze_json_dict(await hardware.get_system_capabilities())
        if "gpu_discovery" in capabilities:
            return capabilities, None
        inventory = freeze_json_dict(
            await hardware.get_system_info(
                components=["gpu"], cache=False, include_gpu_capabilities=False
            )
        )
    except OBSERVATION_EXCEPTIONS as exception:
        log_handled_exception(
            manager.logger,
            exception,
            message="Backend runtime compatibility observations are unavailable.",
            operation=OPERATION_OBSERVE_COMPATIBILITY,
            details={"plugin": plugin_name},
            level="debug",
        )
        return capabilities, None
    return capabilities, inventory
