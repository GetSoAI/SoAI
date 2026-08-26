"""SoAI - Core plugin error types [backend/core/plugins/errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, override

from core.errors.exceptions import ValidationError
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.state.compatibility import CompatibilityInfo

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "PluginCapabilityError",
    "PluginIncompatibleError",
)


class PluginIncompatibleError(ValidationError):

    def __init__(
        self,
        plugin_name: str,
        compatibility: CompatibilityInfo,
        plugin_class: type[PluginInstanceProtocol] | None = None,
        plugin_class_name: str | None = None,
    ) -> None:
        super().__init__(compatibility.message, details={"plugin_name": plugin_name})
        self.plugin_name = plugin_name
        self.compatibility = compatibility
        self.plugin_class = plugin_class
        self.plugin_class_name = plugin_class_name

    @override
    def __str__(self) -> str:
        return self.message

    @override
    def __getnewargs_ex__(
        self,
    ) -> tuple[
        tuple[JSONValue | BaseException | None, ...], Mapping[str, JSONValue | BaseException | None]
    ]:
        return ((self.plugin_name,), {})


class PluginCapabilityError(ValidationError):

    def __init__(self, plugin_name: str, capability: str, message: str) -> None:
        super().__init__(message, details={"plugin_name": plugin_name, "capability": capability})
        self.plugin_name = plugin_name
        self.capability = capability

    @override
    def __str__(self) -> str:
        return self.message

    @override
    def __getnewargs_ex__(
        self,
    ) -> tuple[
        tuple[JSONValue | BaseException | None, ...], Mapping[str, JSONValue | BaseException | None]
    ]:
        return ((self.plugin_name, self.capability, self.message), {})
