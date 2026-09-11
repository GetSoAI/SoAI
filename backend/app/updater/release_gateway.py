"""SoAI - Stable release gateway contract [backend/app/updater/release_gateway.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from urllib.parse import urlsplit

from app.updater.release_contract import require_canonical_release_version
from core.errors.exceptions import ValidationError
from core.meta.software_update_platforms import (
    LINUX_UPDATE_PLATFORMS,
    MACOS_UPDATE_PLATFORMS,
    OS_UPDATE_PLATFORMS,
)
from core.network.urls import require_absolute_http_url

__all__ = (
    "SOAI_RELEASE_DISCOVERY_URL",
    "build_update_archive_gateway_url",
    "build_update_installer_gateway_url",
    "resolve_release_discovery_redirect",
)

SOAI_RELEASE_DISCOVERY_URL = "https://soai.to/update/latest"
SOAI_UPDATE_ARCHIVE_BASE_URL = "https://soai.to/update/archive"
SOAI_UPDATE_INSTALLER_BASE_URL = "https://soai.to/update/installer"
GITHUB_LATEST_RELEASE_PATH_PATTERN = (
    r"/repos/[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100}/releases/latest\Z"
)


def _require_github_latest_release_url(location: str) -> str:
    validated = require_absolute_http_url(location)
    parsed = urlsplit(validated)
    if parsed.scheme.lower() != "https":
        raise ValidationError("Release discovery redirect must use HTTPS.")
    if parsed.hostname is None or parsed.hostname.lower() != "api.github.com":
        raise ValidationError("Release discovery redirect host is invalid.")
    if parsed.port not in {None, 443}:
        raise ValidationError("Release discovery redirect port is invalid.")
    if parsed.username is not None or parsed.password is not None:
        raise ValidationError("Release discovery redirect cannot contain user information.")
    if parsed.query or parsed.fragment:
        raise ValidationError("Release discovery redirect cannot contain a query or fragment.")
    if re.fullmatch(GITHUB_LATEST_RELEASE_PATH_PATTERN, parsed.path) is None:
        raise ValidationError("Release discovery redirect path is invalid.")
    return validated


def resolve_release_discovery_redirect(
    *,
    status_code: int,
    locations: tuple[str, ...],
) -> str:
    if status_code != 302:
        raise ValidationError("Release discovery response must be an HTTP 302 redirect.")
    if len(locations) != 1:
        raise ValidationError("Release discovery response must contain one Location header.")
    return _require_github_latest_release_url(locations[0])


def build_update_archive_gateway_url(
    *,
    version: str,
    edition: str,
    platform_id: str,
) -> str:
    canonical_version = require_canonical_release_version(version)
    archive_platforms = (
        (*LINUX_UPDATE_PLATFORMS, *MACOS_UPDATE_PLATFORMS)
        if edition == "soai-core"
        else OS_UPDATE_PLATFORMS if edition == "soai-os" else ()
    )
    if platform_id not in archive_platforms:
        raise ValidationError("Update platform is invalid for the release edition.")
    return f"{SOAI_UPDATE_ARCHIVE_BASE_URL}/{edition}/{platform_id}/{canonical_version}"


def build_update_installer_gateway_url(
    *,
    version: str,
    edition: str,
    platform_id: str,
) -> str:
    canonical_version = require_canonical_release_version(version)
    if edition != "soai-core" or platform_id != "windows-x64":
        raise ValidationError("Update installer platform is invalid for the release edition.")
    return f"{SOAI_UPDATE_INSTALLER_BASE_URL}/{edition}/{platform_id}/{canonical_version}"
