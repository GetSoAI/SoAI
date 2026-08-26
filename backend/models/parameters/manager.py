"""SoAI - Plugin parameter schema management and classification [backend/models/parameters/manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

from core.di.validation import require_dependencies
from core.logging.protocols import LoggerProtocol
from core.types.json_value import copy_json_dict
from core.validation.identifiers import collapse_identifier
from models.parameters.category_projection import copy_used_parameter_categories
from models.parameters.registration_candidate import (
    ParameterInfo,
    build_parameter_registration_candidate,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "ParameterInfo",
    "ParameterManager",
    "ParameterManagerDependencies",
    "ParameterSchema",
)


@dataclass(frozen=True, slots=True)
class ParameterManagerDependencies:
    logger: LoggerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ParameterManagerDependencies",
            logger=self.logger,
        )


def _log_parameter_manager_initialized(target_logger: LoggerProtocol) -> LoggerProtocol:
    target_logger.debug("Dynamic ParameterManager initialized.")
    return target_logger


class ParameterSchema(TypedDict):
    backends: dict[str, JSONDict]
    parameter_categories_by_plugin: dict[str, JSONDict]


class ParameterManager:

    def __init__(self, deps: ParameterManagerDependencies) -> None:
        self._logger = _log_parameter_manager_initialized(deps.logger)
        self.parameter_schema: ParameterSchema = {
            "backends": {},
            "parameter_categories_by_plugin": {},
        }
        self.unified_cache: dict[str, dict[str, ParameterInfo]] = {}
        self.lock = asyncio.Lock()

    async def initialize(self) -> None:
        async with self.lock:
            rebuilt_cache: dict[str, dict[str, ParameterInfo]] = {}
            backends = self.parameter_schema.get("backends", {})
            for plugin_name, definitions in backends.items():
                categories = self.parameter_schema["parameter_categories_by_plugin"].get(
                    plugin_name,
                    {},
                )
                candidate = build_parameter_registration_candidate(
                    plugin_name,
                    {
                        "parameters": definitions,
                        "parameter_categories": categories,
                    },
                )
                rebuilt_cache[plugin_name] = candidate.cache
            self.unified_cache = rebuilt_cache

    async def register_plugin_parameters(self, plugin_name: str, schema: JSONDict) -> None:
        candidate = build_parameter_registration_candidate(plugin_name, schema)
        async with self.lock:
            self.parameter_schema["backends"][plugin_name] = candidate.definitions
            if candidate.categories:
                self.parameter_schema["parameter_categories_by_plugin"][
                    plugin_name
                ] = candidate.categories
            else:
                self.parameter_schema["parameter_categories_by_plugin"].pop(plugin_name, None)
            self.unified_cache[plugin_name] = candidate.cache
            self._logger.debug(
                "Registered and cached parameter schema for plugin '%s'.",
                plugin_name,
            )

    async def unregister_plugin_parameters(self, plugin_name: str) -> None:
        async with self.lock:
            self.parameter_schema["backends"].pop(plugin_name, None)
            self.parameter_schema["parameter_categories_by_plugin"].pop(plugin_name, None)
            self.unified_cache.pop(plugin_name, None)
            self._logger.debug("Unregistered parameter schema for plugin '%s'.", plugin_name)

    async def classify_parameters(
        self,
        plugin_name: str,
        parameters: JSONDict,
    ) -> tuple[JSONDict, JSONDict]:
        startup: JSONDict = {}
        inference: JSONDict = {}
        if not (plugin_name and parameters):
            return (startup, inference)
        async with self.lock:
            plugin_cache = self.unified_cache.get(plugin_name, {})
            for name, value in parameters.items():
                parameter_info = plugin_cache.get(collapse_identifier(name))
                if parameter_info is None:
                    continue
                group = parameter_info["definition"].get("group")
                if group == "startup":
                    startup[name] = value
                elif group == "inference":
                    inference[name] = value
        return (startup, inference)

    async def get_all_parameters_for_plugin(self, plugin_name: str) -> JSONDict:
        async with self.lock:
            return copy_json_dict(self.parameter_schema["backends"].get(plugin_name, {}))

    async def get_parameter_schema_snapshot(self, plugin_name: str) -> tuple[JSONDict, JSONDict]:
        async with self.lock:
            schema = self.parameter_schema["backends"].get(plugin_name)
            if not schema:
                return ({}, {})
            schema_copy = copy_json_dict(schema)
            plugin_categories = self.parameter_schema["parameter_categories_by_plugin"].get(
                plugin_name,
                {},
            )
            return (
                schema_copy,
                copy_used_parameter_categories(schema_copy, plugin_categories),
            )
