"""SoAI - Software update status query [backend/app/updater/software_update/status_query.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.application_dependencies import ApplicationUpdaterModuleDependencies
from app.updater.release_fetch import fetch_latest_release_sync
from core.errors.exception_logging import log_exception
from core.logging.protocols import LoggerProtocol

if TYPE_CHECKING:
    from app.updater.dependencies import SoftwareUpdateServiceDependencies
    from core.types.json import JSONDict

__all__ = (
    "get_software_update_status",
    "get_software_update_status_for_dependencies",
)

OPERATION = "application_updater.get_software_update_status"


def get_software_update_status(
    *,
    timeout: float,
    logger: LoggerProtocol,
    module_dependencies: ApplicationUpdaterModuleDependencies,
    local_version: str | None,
    github_token: str | None = None,
) -> tuple[JSONDict, JSONDict] | None:
    success, latest_release, _ = fetch_latest_release_sync(
        timeout=timeout,
        logger=logger,
        module_dependencies=module_dependencies,
        github_token=github_token,
    )
    if not success or latest_release is None:
        return None
    try:
        update_status = module_dependencies.build_update_status(local_version, latest_release)
        if not isinstance(update_status, dict):
            return None
        return (update_status, latest_release)
    except (TypeError, ValueError) as exception:
        log_exception(
            logger,
            exception,
            message="Failed to determine latest release version",
            operation=OPERATION,
        )
        return None


def get_software_update_status_for_dependencies(
    deps: SoftwareUpdateServiceDependencies,
) -> tuple[JSONDict, JSONDict] | None:
    return get_software_update_status(
        timeout=deps.timeout,
        logger=deps.logger,
        module_dependencies=deps.module_dependencies,
        local_version=deps.local_version,
        github_token=deps.config.get_str("MODELS.CREDENTIALS.GITHUB_TOKEN"),
    )
