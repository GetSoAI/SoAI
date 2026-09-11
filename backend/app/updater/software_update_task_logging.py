"""SoAI - Software update task logging helper [backend/app/updater/software_update_task_logging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.updater.internal_protocols import UpdaterApiClientProtocol
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.system_api.route_paths import SOAI_TASKS_PREFIX
from core.validation.runtime import is_success_payload

if TYPE_CHECKING:
    from app.updater.dependencies import SoftwareUpdateServiceDependencies

__all__ = (
    "log_software_update_task",
    "log_software_update_task_for_dependencies",
)

OPERATION = "application_updater.software_update.log_task"
TASK_LOGGING_EXCEPTIONS = RECOVERABLE_EXCEPTIONS + (SoAIError,)


def log_software_update_task(
    *,
    logger: LoggerProtocol,
    api_client: UpdaterApiClientProtocol,
    api_timeout: float,
    task_id: str,
    from_version: str,
    to_version: str,
    status: str,
    message: str | None = None,
) -> bool:
    try:
        base_url, request_headers, ssl_context = api_client.get_base_url_and_auth_headers(
            timeout=api_timeout,
        )
        if not request_headers:
            logger.debug("Skipping software update task logging: no updater session configured")
            return False
        result = api_client.make_api_request(
            method="POST",
            url=f"{base_url}{SOAI_TASKS_PREFIX}/software-update/log",
            timeout=api_timeout,
            headers=request_headers,
            body={
                "task_id": task_id,
                "from_version": from_version,
                "to_version": to_version,
                "status": status,
                "message": message,
            },
            ssl_context=ssl_context,
        )
        if is_success_payload(
            result,
            logger,
            operation="application_updater.software_update.is_success_payload",
            recover_message=(
                "Failed to parse success flag from software update payload (non-critical)."
            ),
            default=False,
        ):
            logger.debug("Logged software update task: %s", status)
            return True
    except TASK_LOGGING_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to log software update task (non-critical).",
            operation=OPERATION,
            details={"status": status},
            level="debug",
        )
    return False


def log_software_update_task_for_dependencies(
    deps: SoftwareUpdateServiceDependencies,
    *,
    task_id: str,
    to_version: str,
    status: str,
    message: str | None = None,
) -> bool:
    return log_software_update_task(
        logger=deps.logger,
        api_client=deps.api_client,
        api_timeout=deps.api_timeout,
        task_id=task_id,
        from_version=deps.local_version or "unknown",
        to_version=to_version,
        status=status,
        message=message,
    )
