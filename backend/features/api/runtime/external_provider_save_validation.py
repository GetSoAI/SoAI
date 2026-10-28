"""SoAI - External provider save-time validation policy [backend/features/api/runtime/external_provider_save_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.network.errors import NetworkPolicyError
from core.runtime.network_policy import OfflineModeError, validate_local_only_url
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.types.json import JSONValue
from features.api.runtime.external_provider_validation import (
    ExternalProviderValidationResult,
    validate_external_provider_live,
)

__all__ = (
    "evaluate_external_provider_discovery_skip",
    "should_skip_external_provider_discovery",
    "validate_external_provider_for_save",
)


def should_skip_external_provider_discovery(
    validation: ExternalProviderValidationResult,
) -> bool:
    return validation.details.get("status") == "offline_remote_skipped"


def _offline_validation_skipped_result(
    api_url: str,
    message: str,
) -> ExternalProviderValidationResult:
    return ExternalProviderValidationResult(
        ok=True,
        message=message,
        details={
            "ok": True,
            "api_url": api_url,
            "status": "offline_remote_skipped",
            "message": message,
        },
    )


async def evaluate_external_provider_discovery_skip(
    runtime_flags: RuntimeFlagsViewProtocol,
    *,
    api_url: str,
    source: str,
) -> ExternalProviderValidationResult | None:
    normalized_url = str(api_url or "").strip()
    if not runtime_flags.offline_mode:
        return None
    try:
        await validate_local_only_url(runtime_flags, normalized_url, source=source)
    except OfflineModeError:
        return _offline_validation_skipped_result(
            normalized_url,
            "Model discovery skipped because SYSTEM.RUNTIME.STAY_OFFLINE is enabled and the provider URL is not local.",
        )
    except NetworkPolicyError:
        return _offline_validation_skipped_result(
            normalized_url,
            "Model discovery skipped because SYSTEM.RUNTIME.STAY_OFFLINE is enabled and the provider URL is not local.",
        )
    return None


async def validate_external_provider_for_save(
    runtime_flags: RuntimeFlagsViewProtocol,
    *,
    api_url: str,
    api_key: str | None,
    extra_headers: Mapping[str, JSONValue] | None,
    extra_query_params: Mapping[str, JSONValue] | None,
    source: str,
) -> ExternalProviderValidationResult:
    normalized_url = str(api_url or "").strip()
    if runtime_flags.offline_mode:
        try:
            await validate_local_only_url(runtime_flags, normalized_url, source=source)
        except OfflineModeError:
            return _offline_validation_skipped_result(
                normalized_url,
                "Live provider validation skipped because SYSTEM.RUNTIME.STAY_OFFLINE is enabled and the provider URL is not local.",
            )
        except NetworkPolicyError:
            return _offline_validation_skipped_result(
                normalized_url,
                "Live provider validation skipped because SYSTEM.RUNTIME.STAY_OFFLINE is enabled and the provider URL is not local.",
            )
    return await validate_external_provider_live(
        runtime_flags,
        api_url=normalized_url,
        api_key=api_key,
        extra_headers=extra_headers,
        extra_query_params=extra_query_params,
    )
