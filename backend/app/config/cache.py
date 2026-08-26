"""SoAI - Configuration cache with thread-safe operations [backend/app/config/cache.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass

from ruamel.yaml.comments import CommentedMap

from app.config.internal_protocols import ConfigIOProtocol
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConfigurationError
from core.logging.protocols import LoggerProtocol

__all__ = (
    "ConfigCache",
    "ConfigCacheDependencies",
)

OPERATION = "config_cache.load"


@dataclass(frozen=True, slots=True)
class ConfigCacheDependencies:
    logger: LoggerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ConfigCacheDependencies",
            logger=self.logger,
        )


class ConfigCache:
    def __init__(self, deps: ConfigCacheDependencies) -> None:
        self._deps = deps
        self.configs: dict[str, CommentedMap] = {}
        self.lock = asyncio.Lock()

    async def get(self, config_name: str) -> CommentedMap | None:
        async with self.lock:
            config_data = self.configs.get(config_name)
            return copy.deepcopy(config_data) if config_data is not None else None

    async def set(self, config_name: str, data: CommentedMap) -> None:
        async with self.lock:
            self.configs[config_name] = copy.deepcopy(data)

    async def delete(self, config_name: str) -> bool:
        async with self.lock:
            removed = self.configs.pop(config_name, None)
            if removed is not None:
                self._deps.logger.debug("Removed '%s' from configuration cache.", config_name)
                return True
            return False

    async def load(
        self,
        config_name: str,
        io_component: ConfigIOProtocol,
        force_reload: bool = False,
    ) -> CommentedMap | None:
        async with self.lock:
            if not force_reload and config_name in self.configs:
                return copy.deepcopy(self.configs[config_name])
        try:
            data = await io_component.read_config_from_disk(config_name=config_name)
        except ConfigurationError as exception:
            log_exception(
                self._deps.logger,
                exception,
                message="Failed to load configuration",
                operation=OPERATION,
                details={"config_name": config_name},
            )
            raise
        if data is not None:
            async with self.lock:
                self.configs[config_name] = data
            self._deps.logger.debug("Successfully loaded configuration for '%s'.", config_name)
            return copy.deepcopy(data)
        return None
