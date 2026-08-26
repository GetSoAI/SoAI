"""SoAI - Bootstrap YAML loading utilities [backend/app/bootstrap_yaml_loader.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ConfigurationError
from core.filesystem.async_queries import async_path_exists
from core.filesystem.open_files import open_text

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict, ConfigValue
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONValue

__all__ = (
    "load_and_parse_yaml",
    "normalize_loaded_config",
)

OPERATION_APP_BOOTSTRAP_YAML_LOAD = "app.bootstrap_yaml_loader.load"


def normalize_loaded_config(
    data: ConfigValue | JSONValue,
    *,
    config_path: str,
    logger: LoggerProtocol,
    coerce_item: Callable[[ConfigValue | JSONValue], ConfigValue],
) -> ConfigDict | None:
    if data is None:
        return None
    try:
        coerced = coerce_item(data)
    except ConfigurationError as exception:
        log_handled_exception(
            logger,
            exception,
            message="Configuration file normalization failed. It will be treated as missing.",
            operation=OPERATION_APP_BOOTSTRAP_YAML_LOAD,
            details={"path": config_path},
        )
        return None
    if not isinstance(coerced, dict):
        logger.warning("Configuration file at '%s' must contain a YAML mapping.", config_path)
        return None
    return coerced


async def load_and_parse_yaml(
    path: str,
    *,
    yaml_loader: YAML | None,
    logger: LoggerProtocol,
    normalize: Callable[[ConfigValue | JSONValue], ConfigDict | None],
) -> ConfigDict | None:
    def _sync_load_and_parse() -> ConfigDict | None:
        with open_text(path, encoding="utf-8") as handle:
            content = handle.read()
        if not content.strip():
            logger.warning(
                "Configuration file at '%s' is empty. It will be treated as missing.",
                path,
            )
            return None
        if yaml_loader is None:
            logger.critical(
                "CRITICAL: Core dependency 'ruamel.yaml' not installed. Entering DEGRADED MODE.",
            )
            return None
        try:
            loaded = yaml_loader.load(content)
        except YAMLError as error:
            log_handled_exception(
                logger,
                error,
                message=(
                    "Configuration file is corrupt or invalid YAML. "
                    "It will be treated as missing."
                ),
                operation=OPERATION_APP_BOOTSTRAP_YAML_LOAD,
                details={"path": path},
            )
            return None
        return normalize(loaded)

    if not await async_path_exists(path):
        return None
    return await asyncio.to_thread(_sync_load_and_parse)
