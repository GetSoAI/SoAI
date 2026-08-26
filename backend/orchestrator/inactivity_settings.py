"""SoAI - Inactivity monitor settings parsing [backend/orchestrator/inactivity_settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.numeric import coerce_positive_int
from core.errors.exceptions import ValidationError
from core.validation.boolean_coercion import coerce_bool

if TYPE_CHECKING:
    from core.config.protocols import ConfigValue
    from core.types.json import JSONValue

__all__ = ("InactivityMonitorSettings", "resolve_inactivity_monitor_settings")


@dataclass(frozen=True, slots=True)
class InactivityMonitorSettings:
    system_enabled: bool
    system_timeout_seconds: int
    system_action: str
    models_enabled: bool
    models_timeout_seconds: int
    check_interval_seconds: int


def resolve_inactivity_monitor_settings(
    config_section: JSONValue | ConfigValue,
) -> InactivityMonitorSettings:
    if not isinstance(config_section, dict):
        raise ValidationError("SYSTEM.INACTIVITY configuration must be a mapping.")
    system_section = config_section.get("SYSTEM", {}) or {}
    models_section = config_section.get("MODELS", {}) or {}
    if not isinstance(system_section, dict):
        raise ValidationError("SYSTEM.INACTIVITY.SYSTEM must be a mapping.")
    if not isinstance(models_section, dict):
        raise ValidationError("SYSTEM.INACTIVITY.MODELS must be a mapping.")
    system_enabled_value = system_section.get("ENABLED", False)
    if (
        not isinstance(system_enabled_value, str | int | float | bool | bytes | bytearray)
        and system_enabled_value is not None
    ):
        raise ValidationError("SYSTEM.INACTIVITY.SYSTEM.ENABLED must be a boolean.")
    system_enabled = coerce_bool(system_enabled_value, default=False)
    system_timeout = coerce_positive_int(
        system_section.get("TIMEOUT_MINUTES", 30),
        default=30,
        minimum=0,
    )
    system_action_raw = system_section.get("ACTION", "shutdown")
    system_action = str(system_action_raw or "").strip().lower() or "shutdown"
    if system_action not in {"shutdown", "unload_models"}:
        raise ValidationError(
            "SYSTEM.INACTIVITY.SYSTEM.ACTION must be one of: shutdown, unload_models.",
        )
    models_enabled_value = models_section.get("ENABLED", False)
    if (
        not isinstance(models_enabled_value, str | int | float | bool | bytes | bytearray)
        and models_enabled_value is not None
    ):
        raise ValidationError("SYSTEM.INACTIVITY.MODELS.ENABLED must be a boolean.")
    models_enabled = coerce_bool(models_enabled_value, default=False)
    models_timeout = coerce_positive_int(
        models_section.get("TIMEOUT_MINUTES", 10),
        default=10,
        minimum=0,
    )
    check_interval = coerce_positive_int(
        config_section.get("CHECK_INTERVAL_SEC", 15),
        default=15,
        minimum=1,
    )
    return InactivityMonitorSettings(
        system_enabled=system_enabled,
        system_timeout_seconds=system_timeout * 60,
        system_action=system_action,
        models_enabled=models_enabled,
        models_timeout_seconds=models_timeout * 60,
        check_interval_seconds=check_interval,
    )
