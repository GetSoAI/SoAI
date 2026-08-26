"""SoAI - Exact GitHub release asset resolution [backend/app/updater/release_assets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from app.updater.release_contract import (
    checksum_asset_name,
    release_manifest_asset_name,
    release_manifest_signature_asset_name,
)
from app.updater.release_manifest_types import ReleaseUpdateArchive
from core.errors.exceptions import ValidationError
from core.network.urls import require_absolute_http_url

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "ReleaseAsset",
    "ResolvedReleaseAssets",
    "resolve_manifest_assets",
    "resolve_release_assets",
)


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    name: str
    url: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class ResolvedManifestAssets:
    manifest: ReleaseAsset
    signature: ReleaseAsset


@dataclass(frozen=True, slots=True)
class ResolvedReleaseAssets:
    manifest: ReleaseAsset
    signature: ReleaseAsset
    archive: ReleaseAsset
    checksum: ReleaseAsset


def _release_asset_map(
    release_info: Mapping[str, JSONValue],
) -> dict[str, ReleaseAsset]:
    raw_assets = release_info.get("assets")
    if not isinstance(raw_assets, list):
        raise ValidationError("GitHub release assets must be an array.")
    assets: dict[str, ReleaseAsset] = {}
    for raw_asset in raw_assets:
        if not isinstance(raw_asset, dict):
            raise ValidationError("GitHub release asset entry must be an object.")
        name = raw_asset.get("name")
        url = raw_asset.get("browser_download_url")
        size_bytes = raw_asset.get("size")
        if not isinstance(name, str) or not name or "/" in name or "\\" in name:
            raise ValidationError("GitHub release asset name is invalid.")
        if name in assets:
            raise ValidationError(f"GitHub release contains duplicate release asset: {name}")
        if not isinstance(url, str):
            raise ValidationError(f"GitHub release asset must use HTTPS: {name}")
        validated_url = require_absolute_http_url(url)
        if urlsplit(validated_url).scheme.lower() != "https":
            raise ValidationError(f"GitHub release asset must use HTTPS: {name}")
        if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes <= 0:
            raise ValidationError(f"GitHub release asset size is invalid: {name}")
        assets[name] = ReleaseAsset(name=name, url=validated_url, size_bytes=size_bytes)
    return assets


def _require_asset(assets: dict[str, ReleaseAsset], name: str) -> ReleaseAsset:
    asset = assets.get(name)
    if asset is None:
        raise ValidationError(f"GitHub release is missing required asset: {name}")
    return asset


def resolve_manifest_assets(
    release_info: Mapping[str, JSONValue],
    *,
    version: str,
    edition: str,
) -> ResolvedManifestAssets:
    assets = _release_asset_map(release_info)
    return ResolvedManifestAssets(
        manifest=_require_asset(assets, release_manifest_asset_name(version, edition=edition)),
        signature=_require_asset(
            assets, release_manifest_signature_asset_name(version, edition=edition)
        ),
    )


def resolve_release_assets(
    release_info: Mapping[str, JSONValue],
    *,
    archive: ReleaseUpdateArchive,
    version: str,
    edition: str,
) -> ResolvedReleaseAssets:
    assets = _release_asset_map(release_info)
    return ResolvedReleaseAssets(
        manifest=_require_asset(assets, release_manifest_asset_name(version, edition=edition)),
        signature=_require_asset(
            assets, release_manifest_signature_asset_name(version, edition=edition)
        ),
        archive=_require_asset(assets, archive.name),
        checksum=_require_asset(assets, checksum_asset_name(archive.name)),
    )
