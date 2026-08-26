"""SoAI - OAuth runtime URL policy enforcement [backend/core/oauth/url_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.oauth.management_urls import require_https_url
from core.oauth.protocols import OAuthRuntimeUrlValidator
from core.runtime.network_policy import validate_runtime_url
from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = (
    "create_oauth_runtime_url_validator",
    "validate_oauth_runtime_url",
)


async def validate_oauth_runtime_url(
    runtime_flags: RuntimeFlagsViewProtocol,
    url: str,
    source: str,
) -> None:
    require_https_url(url, source)
    await validate_runtime_url(runtime_flags, url, source=source)


def create_oauth_runtime_url_validator(
    runtime_flags: RuntimeFlagsViewProtocol,
) -> OAuthRuntimeUrlValidator:
    async def validate_url(url: str, source: str) -> None:
        await validate_oauth_runtime_url(runtime_flags, url, source)

    return validate_url
