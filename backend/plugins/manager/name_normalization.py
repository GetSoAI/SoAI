"""SoAI - Plugin manager name normalization helpers [backend/plugins/manager/name_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.plugins.name_validation import require_plugin_name
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = (
    "call_with_optional_plugin_name",
    "call_with_required_plugin_name",
    "normalize_if_state_available",
    "normalize_optional_plugin_name",
    "normalize_or_original",
    "normalize_required_plugin_name",
)


def normalize_if_state_available(
    manager: PluginManagerRuntimeProtocol,
    normalized_plugin_name: str,
) -> str | None:
    return manager.normalize_plugin_name(normalized_plugin_name)


def normalize_optional_plugin_name(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> str | None:
    normalized_plugin_name = coerce_optional_trimmed_str(plugin_name)
    if normalized_plugin_name is None:
        return None
    return normalize_if_state_available(manager, normalized_plugin_name)


def normalize_required_plugin_name(manager: PluginManagerRuntimeProtocol, plugin_name: str) -> str:
    normalized_plugin_name = require_plugin_name(plugin_name)
    canonical_name = normalize_if_state_available(manager, normalized_plugin_name)
    if canonical_name is None:
        raise ValidationError(f"Plugin '{normalized_plugin_name}' not found.")
    return canonical_name


def normalize_or_original(value: str) -> str:
    normalized_value = value.strip()
    return normalized_value or value


async def call_with_optional_plugin_name[T](
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    fallback: T,
    operation: Callable[[PluginManagerRuntimeProtocol, str], Awaitable[T]],
) -> T:
    normalized_plugin_name = normalize_optional_plugin_name(manager, plugin_name)
    if normalized_plugin_name is None:
        return fallback
    return await operation(manager, normalized_plugin_name)


async def call_with_required_plugin_name[T](
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    operation: Callable[[PluginManagerRuntimeProtocol, str], Awaitable[T]],
) -> T:
    normalized_plugin_name = normalize_required_plugin_name(manager, plugin_name)
    return await operation(manager, normalized_plugin_name)
