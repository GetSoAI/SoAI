"""SoAI - Signed release bundle preparation [backend/app/updater/release_bundle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.edition_composition import UpdaterComposition
from app.updater.networking import open_url
from app.updater.release_assets import (
    ResolvedReleaseAssets,
    resolve_manifest_assets,
    resolve_release_assets,
)
from app.updater.release_gateway import build_update_archive_gateway_url
from app.updater.release_manifest import (
    parse_release_manifest_bytes,
    select_update_archive,
)
from app.updater.release_manifest_types import ReleaseManifestV1, ReleaseUpdateArchive
from app.updater.release_signature import (
    release_public_key_fingerprint,
    verify_release_manifest_signature,
)
from core.errors.exceptions import ValidationError
from core.errors.external_service_exception import ExternalServiceError
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "PreparedReleaseBundle",
    "prepare_release_bundle",
    "release_public_key_path",
)

MAX_RELEASE_MANIFEST_BYTES = 64 * 1024 * 1024
MAX_RELEASE_SIGNATURE_BYTES = 1024
MAX_RELEASE_CHECKSUM_BYTES = 1024


@dataclass(frozen=True, slots=True)
class PreparedReleaseBundle:
    manifest: ReleaseManifestV1
    archive_record: ReleaseUpdateArchive
    assets: ResolvedReleaseAssets
    expected_archive_sha256: str
    archive_download_url: str
    updater: UpdaterComposition


def release_public_key_path() -> str:
    return os.path.join(os.path.dirname(__file__), "release_public_key.txt")


def _download_bounded_asset(
    *,
    url: str,
    timeout: float,
    maximum_bytes: int,
    label: str,
) -> bytes:
    try:
        with open_url(
            url,
            timeout=timeout,
            offline_mode=False,
            artifact_download=True,
        ) as response:
            if response.status_code != 200:
                raise ExternalServiceError(
                    f"{label} download returned HTTP {response.status_code}."
                )
            content_length = response.headers.get("Content-Length")
            declared_bytes: int | None = None
            if content_length is not None:
                try:
                    declared_bytes = int(content_length)
                except ValueError as exception:
                    raise ExternalServiceError(f"{label} Content-Length is invalid.") from exception
                if declared_bytes < 0 or declared_bytes > maximum_bytes:
                    raise ValidationError(f"{label} exceeds its maximum allowed size.")
            chunks: list[bytes] = []
            received_bytes = 0
            for chunk in response.iter_bytes():
                if not chunk:
                    continue
                received_bytes += len(chunk)
                if received_bytes > maximum_bytes:
                    raise ValidationError(f"{label} exceeds its maximum allowed size.")
                chunks.append(chunk)
            if received_bytes == 0:
                raise ValidationError(f"{label} is empty.")
            if declared_bytes is not None and received_bytes != declared_bytes:
                raise ExternalServiceError(f"{label} download was truncated.")
            return b"".join(chunks)
    except HTTP_RECOVERABLE_EXCEPTIONS as exception:
        raise ExternalServiceError(f"{label} download failed.", cause=exception) from exception


def _parse_checksum_sidecar(sidecar_bytes: bytes, *, archive: ReleaseUpdateArchive) -> str:
    try:
        sidecar_text = sidecar_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exception:
        raise ValidationError("Release checksum sidecar must be valid UTF-8.") from exception
    expected_line = f"{archive.sha256}  {archive.name}\n"
    if sidecar_text != expected_line:
        raise ValidationError("Release checksum sidecar does not exactly match the signed archive.")
    return archive.sha256


def _require_asset_size(content: bytes, *, expected_size: int, label: str) -> None:
    if len(content) != expected_size:
        raise ValidationError(f"{label} size does not match the GitHub release asset record.")


def _require_installed_core_compatibility(
    manifest: ReleaseManifestV1,
    updater: UpdaterComposition,
) -> None:
    if updater.edition == "soai-os" and manifest.core_version != updater.core_version:
        raise ValidationError(
            "SoAI OS release Core version does not match the installed Core version."
        )


def prepare_release_bundle(
    *,
    release_info: Mapping[str, JSONValue],
    version: str,
    platform_id: str,
    timeout: float,
    public_key_path: str | None = None,
    updater: UpdaterComposition,
) -> PreparedReleaseBundle:
    manifest_assets = resolve_manifest_assets(
        release_info,
        version=version,
        edition=updater.edition,
    )
    manifest_bytes = _download_bounded_asset(
        url=manifest_assets.manifest.url,
        timeout=timeout,
        maximum_bytes=MAX_RELEASE_MANIFEST_BYTES,
        label="Release manifest",
    )
    signature_bytes = _download_bounded_asset(
        url=manifest_assets.signature.url,
        timeout=timeout,
        maximum_bytes=MAX_RELEASE_SIGNATURE_BYTES,
        label="Release manifest signature",
    )
    _require_asset_size(
        manifest_bytes,
        expected_size=manifest_assets.manifest.size_bytes,
        label="Release manifest",
    )
    _require_asset_size(
        signature_bytes,
        expected_size=manifest_assets.signature.size_bytes,
        label="Release manifest signature",
    )
    selected_public_key_path = public_key_path or release_public_key_path()
    verify_release_manifest_signature(
        manifest_bytes=manifest_bytes,
        signature_bytes=signature_bytes,
        public_key_path=selected_public_key_path,
    )
    manifest = parse_release_manifest_bytes(
        manifest_bytes,
        expected_version=version,
        expected_edition=updater.edition,
    )
    if manifest.public_trust.release_signing_key_sha256 != release_public_key_fingerprint(
        selected_public_key_path
    ):
        raise ValidationError("Release manifest public trust does not match the signing key.")
    _require_installed_core_compatibility(manifest, updater)
    archive_record = select_update_archive(manifest, platform_id=platform_id)
    assets = resolve_release_assets(
        release_info,
        archive=archive_record,
        version=version,
        edition=updater.edition,
    )
    if assets.archive.size_bytes != archive_record.size_bytes:
        raise ValidationError("GitHub archive size does not match the signed release manifest.")
    checksum_bytes = _download_bounded_asset(
        url=assets.checksum.url,
        timeout=timeout,
        maximum_bytes=MAX_RELEASE_CHECKSUM_BYTES,
        label="Release checksum",
    )
    _require_asset_size(
        checksum_bytes,
        expected_size=assets.checksum.size_bytes,
        label="Release checksum",
    )
    expected_archive_sha256 = _parse_checksum_sidecar(
        checksum_bytes,
        archive=archive_record,
    )
    archive_download_url = build_update_archive_gateway_url(
        version=manifest.version,
        edition=manifest.edition,
        platform_id=platform_id,
    )
    return PreparedReleaseBundle(
        manifest=manifest,
        archive_record=archive_record,
        assets=assets,
        expected_archive_sha256=expected_archive_sha256,
        archive_download_url=archive_download_url,
        updater=updater,
    )
