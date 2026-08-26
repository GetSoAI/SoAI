"""SoAI - Hardware manager variant support context builder [backend/hardware/manager/variant_support_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.hardware.variant_support import VariantSupportContext
from core.validation.booleans import parse_bool
from hardware.variant_support_context_payload import (
    build_variant_support_context_payload,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.hardware.protocols import DatabaseHardwareProtocol
    from core.types.json import JSONDict
    from core.types.protocols import HttpClientProtocol
    from hardware.manager.computed_config import HardwareManagerComputedConfig
    from hardware.manager.dependencies import HardwareManagerDependencies

__all__ = ("build_variant_support_context",)


async def build_variant_support_context(
    *,
    deps: HardwareManagerDependencies,
    computed: HardwareManagerComputedConfig,
    models_dir: str | None,
    include_speed_tests: bool,
    get_system_capabilities: Callable[[], Awaitable[JSONDict]],
    database_hardware: DatabaseHardwareProtocol | None,
    http_client: HttpClientProtocol | None,
) -> VariantSupportContext:
    require_measurements = parse_bool(
        computed.config_dict.get("VARIANT_SPEED_TEMPLATES_REQUIRE_MEASUREMENTS", True),
        default=True,
    )
    capabilities = await get_system_capabilities()
    return await build_variant_support_context_payload(
        capabilities=capabilities,
        models_dir=models_dir,
        include_speed_tests=include_speed_tests,
        disk_speed_test_service=deps.disk_speed_test_service,
        network_speed_test_service=deps.network_speed_test_service,
        database_hardware=database_hardware,
        http_client=http_client,
        require_measurements=require_measurements,
    )
