"""SoAI - Application update checker service [backend/plugins/updater.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2

from core.config.protocols import ConfigProtocol
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, ValidationError
from core.logging.trace import get_logger
from core.meta.software_update_platforms import (
    delivery_type_for_platform,
    supported_update_platforms_for_edition,
)
from core.meta.versioning import build_update_status, get_core_version
from core.plugins.protocols_guardian import UpdaterModuleDependenciesProtocol
from core.runtime.platform import get_runtime_platform
from plugins.protocols_internal.runtime.internal_protocols import (
    FetchLatestSoAIReleaseAsyncProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("Updater",)

LOGGER_NAME = "SoAI.plugins.updater"
OPERATION = "plugin_types.updater.build_update_status"


class Updater:
    def __init__(
        self,
        config: ConfigProtocol,
        http_client: httpx2.AsyncClient,
        module_dependencies: UpdaterModuleDependenciesProtocol,
        *,
        edition: str,
        module_dependencies_type: type[UpdaterModuleDependenciesProtocol],
        fetch_latest_release_async: FetchLatestSoAIReleaseAsyncProtocol,
    ) -> None:
        if not isinstance(module_dependencies, module_dependencies_type):
            raise ValidationError("ApplicationUpdaterModuleDependencies are required.")
        self.config = config
        self.http_client = http_client
        self.timeout = config.get_float("SYSTEM.UPDATER.TIMEOUT_SEC")
        self.github_token = config.get_str("MODELS.CREDENTIALS.GITHUB_TOKEN")
        self.module_dependencies = module_dependencies
        self.fetch_latest_release_async = fetch_latest_release_async
        self.supported_platforms = supported_update_platforms_for_edition(edition)

    async def check_for_app_update(self) -> JSONDict:
        logger = get_logger(LOGGER_NAME)
        platform_id = get_runtime_platform().platform_id
        delivery_type = (
            delivery_type_for_platform(platform_id)
            if platform_id in self.supported_platforms
            else None
        )
        platform_status: JSONDict = {
            "platform_id": platform_id,
            "delivery_type": delivery_type,
            "install_supported": delivery_type is not None,
        }
        success, release_info, message = await self.fetch_latest_release_async(
            self.http_client,
            timeout=self.timeout,
            logger=logger,
            module_dependencies=self.module_dependencies,
            github_token=self.github_token,
        )
        if not success or release_info is None:
            return {"update_available": False, "message": message, **platform_status}
        try:
            return {
                **build_update_status(get_core_version(), release_info),
                **platform_status,
            }
        except (SoAIError, TypeError, ValueError) as exception:
            log_exception(
                logger,
                exception,
                message="Updater comparison failed.",
                operation=OPERATION,
                level="error",
            )
            return {
                "update_available": False,
                "message": "Release information was invalid.",
                **platform_status,
            }
