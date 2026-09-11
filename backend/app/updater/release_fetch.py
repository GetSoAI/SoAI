"""SoAI - Updater release fetching [backend/app/updater/release_fetch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.updater.release_gateway import (
    SOAI_RELEASE_DISCOVERY_URL,
    resolve_release_discovery_redirect,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, ValidationError
from core.logging.trace import get_logger
from core.meta.version import __version__
from core.network.http_json import read_http_json_dict
from core.network.outbound_http_profiles import (
    build_github_api_headers,
    build_outbound_request_headers,
)
from core.plugins.protocols_guardian import UpdaterModuleDependenciesProtocol

if TYPE_CHECKING:
    import httpx2

    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict

__all__ = (
    "fetch_latest_release_async",
    "fetch_latest_release_sync",
)

LOGGER_NAME = "SoAI.app.updater.release_fetch"
OPERATION_APP_UPDATER_RELEASE_FETCH_ASYNC = "app.updater.release_fetch.async"
OPERATION_APP_UPDATER_RELEASE_FETCH_SYNC = "app.updater.release_fetch.sync"
REQUEST_FAILURE_MESSAGE = "SoAI release request failed."
RESPONSE_FAILURE_MESSAGE = "SoAI release response was invalid."
RELEASE_NOT_FOUND_MESSAGE = "No SoAI release is published."


def _resolve_discovery_response(response: httpx2.Response) -> str:
    if response.status_code >= 400:
        response.raise_for_status()
    return resolve_release_discovery_redirect(
        status_code=response.status_code,
        locations=tuple(response.headers.get_list("Location")),
    )


def _read_release_response(response: httpx2.Response) -> tuple[JSONDict | None, str]:
    if response.status_code == 404:
        return (None, RELEASE_NOT_FOUND_MESSAGE)
    if response.status_code != 200:
        response.raise_for_status()
        raise ValidationError("GitHub release response must use HTTP 200.")
    return (read_http_json_dict(response, field="GitHub release response"), "Success")


def _log_release_fetch_failure(
    *,
    logger: LoggerProtocol,
    exception: Exception,
    message: str,
    operation: str,
    url: str,
) -> None:
    log_exception(
        logger,
        exception,
        message=message,
        operation=operation,
        details={"url": url},
        level="warning",
    )


def fetch_latest_release_sync(
    *,
    timeout: float,
    module_dependencies: UpdaterModuleDependenciesProtocol,
    logger: LoggerProtocol | None = None,
    github_token: str | None = None,
) -> tuple[bool, JSONDict | None, str]:
    http_client_module = module_dependencies.httpx2
    active_url = SOAI_RELEASE_DISCOVERY_URL
    try:
        with http_client_module.Client(timeout=float(timeout)) as client:
            discovery_response = client.get(
                SOAI_RELEASE_DISCOVERY_URL,
                headers=build_outbound_request_headers(
                    profile_type="service_api", extra_headers={"X-SoAI-Version": __version__}
                ),
                follow_redirects=False,
            )
            active_url = _resolve_discovery_response(discovery_response)
            release_response = client.get(
                active_url,
                headers=build_github_api_headers(github_token=github_token),
                follow_redirects=False,
            )
            payload, message = _read_release_response(release_response)
        return (payload is not None, payload, message)
    except (http_client_module.RequestError, http_client_module.HTTPStatusError) as exception:
        resolved_logger = logger or get_logger(LOGGER_NAME)
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_APP_UPDATER_RELEASE_FETCH_SYNC,
            details={"url": active_url},
        )
        _log_release_fetch_failure(
            logger=resolved_logger,
            exception=coerced,
            message=REQUEST_FAILURE_MESSAGE,
            operation=OPERATION_APP_UPDATER_RELEASE_FETCH_SYNC,
            url=active_url,
        )
        return (False, None, REQUEST_FAILURE_MESSAGE)
    except (SoAIError, TypeError, ValueError) as exception:
        resolved_logger = logger or get_logger(LOGGER_NAME)
        _log_release_fetch_failure(
            logger=resolved_logger,
            exception=exception,
            message=RESPONSE_FAILURE_MESSAGE,
            operation=OPERATION_APP_UPDATER_RELEASE_FETCH_SYNC,
            url=active_url,
        )
        return (False, None, RESPONSE_FAILURE_MESSAGE)


async def fetch_latest_release_async(
    http_client: httpx2.AsyncClient,
    *,
    timeout: float,
    module_dependencies: UpdaterModuleDependenciesProtocol,
    logger: LoggerProtocol | None = None,
    github_token: str | None = None,
) -> tuple[bool, JSONDict | None, str]:
    http_client_module = module_dependencies.httpx2
    active_url = SOAI_RELEASE_DISCOVERY_URL
    try:
        discovery_response = await http_client.get(
            SOAI_RELEASE_DISCOVERY_URL,
            headers=build_outbound_request_headers(
                profile_type="service_api", extra_headers={"X-SoAI-Version": __version__}
            ),
            follow_redirects=False,
            timeout=float(timeout),
        )
        active_url = _resolve_discovery_response(discovery_response)
        release_response = await http_client.get(
            active_url,
            headers=build_github_api_headers(github_token=github_token),
            follow_redirects=False,
            timeout=float(timeout),
        )
        payload, message = _read_release_response(release_response)
        return (payload is not None, payload, message)
    except (http_client_module.RequestError, http_client_module.HTTPStatusError) as exception:
        resolved_logger = logger or get_logger(LOGGER_NAME)
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_APP_UPDATER_RELEASE_FETCH_ASYNC,
            details={"url": active_url},
        )
        _log_release_fetch_failure(
            logger=resolved_logger,
            exception=coerced,
            message=REQUEST_FAILURE_MESSAGE,
            operation=OPERATION_APP_UPDATER_RELEASE_FETCH_ASYNC,
            url=active_url,
        )
        return (False, None, REQUEST_FAILURE_MESSAGE)
    except (SoAIError, TypeError, ValueError) as exception:
        resolved_logger = logger or get_logger(LOGGER_NAME)
        _log_release_fetch_failure(
            logger=resolved_logger,
            exception=exception,
            message=RESPONSE_FAILURE_MESSAGE,
            operation=OPERATION_APP_UPDATER_RELEASE_FETCH_ASYNC,
            url=active_url,
        )
        return (False, None, RESPONSE_FAILURE_MESSAGE)
