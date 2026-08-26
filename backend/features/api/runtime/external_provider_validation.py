"""SoAI - External provider live validation helpers [backend/features/api/runtime/external_provider_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx2

from core.errors.exceptions import ValidationError
from core.openai.provider_transport import (
    build_openai_provider_headers,
    compose_openai_provider_url,
    normalize_openai_provider_query_params,
)
from core.runtime.network_http_client import create_guarded_async_http_client
from features.api.runtime.external_provider_live_probe import (
    probe_models_endpoint,
    probe_supported_endpoints,
)
from features.api.runtime.external_provider_probe import (
    KNOWN_OPENAI_PROVIDER_ENDPOINT_SUFFIXES,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ExternalProviderValidationResult",
    "validate_external_provider_live",
)


@dataclass(frozen=True, slots=True)
class ExternalProviderValidationResult:
    ok: bool
    message: str
    details: JSONDict


async def validate_external_provider_live(
    runtime_flags: RuntimeFlagsViewProtocol,
    *,
    api_url: str,
    api_key: str | None,
    extra_headers: Mapping[str, JSONValue] | None,
    extra_query_params: Mapping[str, JSONValue] | None,
    timeout_sec: float = 12.0,
) -> ExternalProviderValidationResult:
    normalized_url = str(api_url or "").strip()
    if not normalized_url:
        return ExternalProviderValidationResult(
            ok=False,
            message="Provider api_url is required.",
            details={"ok": False},
        )
    trimmed_url = normalized_url.rstrip("/")
    entered_endpoint_suffix = next(
        (
            suffix
            for suffix in KNOWN_OPENAI_PROVIDER_ENDPOINT_SUFFIXES
            if trimmed_url.endswith(suffix)
        ),
        None,
    )

    try:
        query_params = normalize_openai_provider_query_params(extra_query_params)
        models_headers = build_openai_provider_headers(
            api_key=api_key,
            extra_headers=extra_headers,
            include_content_type=False,
        )
        probe_headers = build_openai_provider_headers(
            api_key=api_key,
            extra_headers=extra_headers,
            include_content_type=True,
        )
    except ValidationError as exception:
        return ExternalProviderValidationResult(
            ok=False,
            message=str(exception),
            details={
                "ok": False,
                "api_url": normalized_url,
                "models": {"status": "invalid_config"},
                "endpoints": {},
                "warnings": [],
            },
        )
    models_url = compose_openai_provider_url(normalized_url, "/models", query_params)
    details: JSONDict = {
        "ok": False,
        "api_url": normalized_url,
        "models": {"url": models_url, "status": "unknown"},
        "endpoints": {},
        "warnings": [],
    }

    timeout = httpx2.Timeout(timeout_sec)
    async with create_guarded_async_http_client(
        runtime_flags,
        source="external_provider_validation",
        timeout=timeout,
    ) as client:
        models_outcome = await probe_models_endpoint(
            client=client,
            normalized_url=normalized_url,
            models_url=models_url,
            models_headers=models_headers,
            entered_endpoint_suffix=entered_endpoint_suffix,
            timeout_sec=timeout_sec,
        )
        details["models"] = models_outcome.models_entry
        if not models_outcome.ok:
            return ExternalProviderValidationResult(
                ok=False,
                message=models_outcome.error_message or "Provider validation failed.",
                details=details,
            )

        endpoints_outcome = await probe_supported_endpoints(
            client=client,
            normalized_url=normalized_url,
            query_params=query_params,
            probe_headers=probe_headers,
        )
        endpoints = endpoints_outcome.endpoints
        details["endpoints"] = endpoints

        if not endpoints_outcome.present_any:
            return ExternalProviderValidationResult(
                ok=False,
                message="Provider responded to GET /models but does not appear to expose any supported OpenAI inference endpoints at this base URL.",
                details=details,
            )

        if api_key:
            non_missing = [
                entry
                for entry in endpoints.values()
                if isinstance(entry, dict) and entry.get("status") != "missing"
            ]
            auth_failed_all = bool(non_missing) and all(
                isinstance(entry, dict) and entry.get("status") == "auth_failed"
                for entry in non_missing
            )
            if auth_failed_all:
                return ExternalProviderValidationResult(
                    ok=False,
                    message="Authentication failed for provider endpoints (HTTP 401/403).",
                    details=details,
                )
            auth_failed_some = any(
                isinstance(entry, dict) and entry.get("status") == "auth_failed"
                for entry in non_missing
            )
            if auth_failed_some:
                warnings = details.get("warnings")
                if isinstance(warnings, list):
                    warnings.append("Some provider endpoints returned HTTP 401/403 during probes.")
        else:
            auth_failed_all = all(
                isinstance(entry, dict) and entry.get("status") == "auth_failed"
                for entry in endpoints.values()
                if isinstance(entry, dict)
            )
            if auth_failed_all:
                warnings = details.get("warnings")
                if isinstance(warnings, list):
                    warnings.append(
                        "Provider requires an API key for inference endpoints; models can be listed but requests will fail until a key is configured.",
                    )

        details["ok"] = True
        warnings = details.get("warnings")
        if isinstance(warnings, list):
            rate_limited = any(
                isinstance(entry, dict) and entry.get("status") == "rate_limited"
                for entry in endpoints.values()
            )
            if rate_limited:
                warnings.append("Provider returned HTTP 429 during endpoint probes.")
        return ExternalProviderValidationResult(
            ok=True,
            message="OK",
            details=details,
        )
