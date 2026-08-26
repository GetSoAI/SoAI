"""SoAI - Model variant hardware compatibility and capacity assessment [backend/plugins/variant_assessment.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.protocols import DatabaseHardwareProtocol, HardwareManagerProtocol
from core.hardware.variant_support import (
    render_variant_speed_template,
    resolve_variant_support_context,
    variant_support_context_to_dict,
)
from core.hardware.variants import coerce_variant_size_bytes
from core.logging.trace import TraceLogger
from core.models.capacity import evaluate_variant_capacity
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.types.json import is_json_dict
from core.validation.coercion import coerce_float_with_bool, coerce_int
from plugins.manager.model_variants import get_model_variants
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from core.types.protocols import HttpClientProtocol

__all__ = ("PluginVariantAssessor",)

OPERATION = "plugin_types.describe"


class PluginVariantAssessor:

    def __init__(self, trace_logger: TraceLogger) -> None:
        self.logger = trace_logger

    async def describe(
        self,
        manager: PluginManagerRuntimeProtocol,
        plugin_name: str,
        model_id: str,
        *,
        include_speed_tests: bool = False,
        hw_manager: HardwareManagerProtocol | None = None,
        database_plugins: DatabasePluginsProtocol | None = None,
        database_hardware: DatabaseHardwareProtocol | None = None,
        http_client: HttpClientProtocol | None = None,
    ) -> list[JSONDict]:
        normalized_model_id = model_id
        match = re.search("huggingface\\.co/([^/]+/[^/]+)", model_id)
        if match:
            normalized_model_id = match.group(1).strip("/")
            self.logger.debug("Normalized URL to '%s'", normalized_model_id)
        normalized_name = manager.normalize_plugin_name(plugin_name)
        if not normalized_name:
            raise ValidationError(f"Plugin '{plugin_name}' not found.")
        await manager.ensure_plugin_compatible(normalized_name)
        release_after_discovery = await manager.get_plugin_instance(normalized_name) is None
        try:
            variants = await get_model_variants(manager, normalized_name, normalized_model_id)
            instance = await manager.get_plugin_instance(normalized_name)
            if instance is None:
                models_dir = None
            else:
                models_dir = instance.get_models_directory()
        finally:
            if release_after_discovery:
                await uncancel_then_cleanup(
                    manager.release_discovery_plugin_instance(normalized_name),
                )
        active_hw_mgr = (
            hw_manager if hw_manager is not None else manager.dependencies.infrastructure.hw_manager
        )
        active_db_plugins = (
            database_plugins
            if database_plugins is not None
            else manager.dependencies.databases.plugins
        )
        active_db_hardware = (
            database_hardware
            if database_hardware is not None
            else manager.dependencies.databases.hardware
        )
        client = http_client if http_client is not None else manager.dependencies.core.http_client
        support_context = await resolve_variant_support_context(
            active_hw_mgr,
            models_dir,
            include_speed_tests,
            database_hardware=active_db_hardware,
            http_client=client,
            config=None,
        )
        context_data = variant_support_context_to_dict(support_context)
        required_caps: JSONDict = (
            dict(instance.REQUIRED_SYSTEM_CAPABILITIES) if instance is not None else {}
        )
        if not required_caps and active_db_plugins is not None:
            try:
                record = await active_db_plugins.get_plugin_by_name(normalized_name)
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    self.logger,
                    exception,
                    message=(
                        "Failed to load plugin record for required capabilities; "
                        "continuing with defaults (non-critical)."
                    ),
                    operation=OPERATION,
                    details={"plugin_name": normalized_name},
                    level="debug",
                )
                record = None
            if isinstance(record, dict):
                db_caps = record.get("required_system_capabilities")
                if is_json_dict(db_caps):
                    required_caps = db_caps
        compatibility_key = "cpu_gpu"
        compatibility_label = "CPU/GPU compatible"
        if "gpu" in required_caps:
            compatibility_key = "gpu_only"
            compatibility_label = "GPU only"
        disk_free_bytes = coerce_int(context_data.get("disk_free_bytes"))
        available_vram_gb = coerce_float_with_bool(context_data.get("available_vram_gb"))
        total_memory_gb = coerce_float_with_bool(context_data.get("total_memory_gb"))
        system_ram_gb = coerce_float_with_bool(context_data.get("system_ram_gb"))
        disk_template_value = context_data.get("disk_speed_template")
        disk_template = disk_template_value if is_json_dict(disk_template_value) else None
        network_template_value = context_data.get("network_speed_template")
        network_template = network_template_value if is_json_dict(network_template_value) else None
        render_speed = render_variant_speed_template
        for variant in variants:
            disk_fit, vram_fit, total_memory_fit, advisory = evaluate_variant_capacity(
                variant,
                available_vram_gb,
                disk_free_bytes,
                total_memory_gb,
            )
            variant.update(
                {
                    "disk_fit": disk_fit,
                    "vram_fit": vram_fit,
                    "vram_ram_fit": total_memory_fit,
                    "hardware_compatibility": compatibility_key,
                    "hardware_compatibility_label": compatibility_label,
                    "system_ram_available_gb": system_ram_gb,
                    "vram_available_gb": available_vram_gb,
                    "advisory": advisory,
                },
            )
            if disk_free_bytes is not None:
                variant_size_bytes = coerce_variant_size_bytes(variant)
                if variant_size_bytes is not None:
                    try:
                        variant["disk_remaining_gb"] = (
                            float(disk_free_bytes) - float(variant_size_bytes)
                        ) / 1024**3
                    except (TypeError, ValueError, OverflowError):
                        variant["disk_remaining_gb"] = None
            if vram_fit is False or total_memory_fit is False:
                variant["runnable"] = False
            elif (vram_fit is True and (total_memory_fit is True or total_memory_fit is None)) or (
                vram_fit is None and total_memory_fit is True
            ):
                variant["runnable"] = True
            else:
                variant["runnable"] = None
            variant["speed_test"] = render_speed(disk_template, variant)
            variant["network_speed_test"] = render_speed(network_template, variant)
        return variants
