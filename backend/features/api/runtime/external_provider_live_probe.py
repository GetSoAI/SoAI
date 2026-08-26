"""SoAI - External provider live probe helpers [backend/features/api/runtime/external_provider_live_probe.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx2

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import FeatureDisabledError, ValidationError
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.network.http_json import read_http_json_value
from core.openai.provider_transport import compose_openai_provider_url
from core.runtime.network_policy import OfflineModeError
from features.api.runtime.external_provider_probe import (
    OPENAI_PROVIDER_ENDPOINTS_TO_PROBE,
    classify_probe_status,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "EndpointsProbeOutcome",
    "ModelsProbeOutcome",
    "probe_models_endpoint",
    "probe_supported_endpoints",
)

LOGGER_NAME = "SoAI.features.api.external_provider_live_probe"
OPERATION = "api_runtime.external_provider_validation.endpoint_probe"


@dataclass(frozen=True, slots=True)
class ModelsProbeOutcome:
    ok: bool
    models_entry: JSONDict
    error_message: str | None


async def probe_models_endpoint(
    *,
    client: httpx2.AsyncClient,
    normalized_url: str,
    models_url: str,
    models_headers: Mapping[str, str],
    entered_endpoint_suffix: str | None,
    timeout_sec: float,
) -> ModelsProbeOutcome:
    try:
        models_response = await client.get(models_url, headers=models_headers)
    except httpx2.TimeoutException:
        return ModelsProbeOutcome(
            ok=False,
            models_entry={"url": models_url, "status": "timeout"},
            error_message=f"Provider did not respond to GET /models within {timeout_sec:g}s.",
        )
    except httpx2.RequestError:
        return ModelsProbeOutcome(
            ok=False,
            models_entry={"url": models_url, "status": "network_error"},
            error_message=f"Could not connect to provider at {normalized_url}.",
        )
    except (OfflineModeError, FeatureDisabledError) as exception:
        return ModelsProbeOutcome(
            ok=False,
            models_entry={"url": models_url, "status": "blocked"},
            error_message=f"Outbound HTTP request blocked by runtime policy: {exception}",
        )

    models_http_status = int(models_response.status_code)
    if models_http_status == 404:
        error_message = (
            (
                "Provider URL looks like a specific endpoint "
                f"('{entered_endpoint_suffix}'). api_url must be the provider base URL (ending at '/v1' or '/openai/v1'), not an endpoint path."
            )
            if entered_endpoint_suffix is not None
            else (
                "Provider did not expose GET /models at this base URL (HTTP 404). "
                "Check that the base URL includes the correct OpenAI-compatible prefix (commonly '/v1' or '/openai/v1')."
            )
        )
        return ModelsProbeOutcome(
            ok=False,
            models_entry={"url": models_url, "status": "missing", "http_status": 404},
            error_message=error_message,
        )
    if models_http_status in (401, 403):
        return ModelsProbeOutcome(
            ok=False,
            models_entry={
                "url": models_url,
                "status": "auth_failed",
                "http_status": models_http_status,
            },
            error_message="Authentication failed while fetching the provider model list (HTTP 401/403).",
        )
    if models_http_status >= 500:
        return ModelsProbeOutcome(
            ok=False,
            models_entry={
                "url": models_url,
                "status": "server_error",
                "http_status": models_http_status,
            },
            error_message=f"Provider returned a server error for GET /models (HTTP {models_http_status}).",
        )
    if not 200 <= models_http_status <= 299:
        return ModelsProbeOutcome(
            ok=False,
            models_entry={
                "url": models_url,
                "status": "invalid_request",
                "http_status": models_http_status,
            },
            error_message=f"Provider returned an unexpected status for GET /models (HTTP {models_http_status}).",
        )

    try:
        models_json = read_http_json_value(models_response, field="GET /models response")
    except (ValidationError, ValueError):
        return ModelsProbeOutcome(
            ok=False,
            models_entry={"url": models_url, "status": "invalid_json", "http_status": 200},
            error_message="Provider returned a non-JSON response for GET /models.",
        )

    valid_models_shape = False
    if isinstance(models_json, dict):
        data = models_json.get("data")
        valid_models_shape = isinstance(data, list)
    elif isinstance(models_json, list):
        valid_models_shape = True
    if not valid_models_shape:
        return ModelsProbeOutcome(
            ok=False,
            models_entry={"url": models_url, "status": "invalid_shape", "http_status": 200},
            error_message="Provider returned an unexpected JSON shape for GET /models.",
        )

    return ModelsProbeOutcome(
        ok=True,
        models_entry={"url": models_url, "status": "ok", "http_status": 200},
        error_message=None,
    )


@dataclass(frozen=True, slots=True)
class EndpointsProbeOutcome:
    endpoints: JSONDict
    present_any: bool


async def probe_supported_endpoints(
    *,
    client: httpx2.AsyncClient,
    normalized_url: str,
    query_params: dict[str, str],
    probe_headers: Mapping[str, str],
) -> EndpointsProbeOutcome:
    endpoints: JSONDict = {}
    for endpoint in OPENAI_PROVIDER_ENDPOINTS_TO_PROBE:
        url = compose_openai_provider_url(normalized_url, endpoint, query_params)
        http_status: int | None = None
        probe_exception: BaseException | None = None
        try:
            response = await client.post(url, headers=probe_headers, json={})
            http_status = int(response.status_code)
        except httpx2.TimeoutException as exception:
            probe_exception = exception
        except httpx2.RequestError as exception:
            probe_exception = exception
        except (OfflineModeError, FeatureDisabledError) as exception:
            probe_exception = exception
        except HTTP_RECOVERABLE_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation="api_runtime.external_provider_validation.endpoint_probe",
            )
            log_handled_exception(
                get_logger(LOGGER_NAME),
                coerced,
                message="External provider endpoint probe failed (non-critical).",
                operation=OPERATION,
                level="debug",
            )
            probe_exception = coerced
        status = classify_probe_status(http_status, exception=probe_exception)
        endpoints[endpoint] = {"url": url, "status": status, "http_status": http_status}

    present_any = any(
        isinstance(entry, dict) and entry.get("status") != "missing" for entry in endpoints.values()
    )
    return EndpointsProbeOutcome(endpoints=endpoints, present_any=present_any)
