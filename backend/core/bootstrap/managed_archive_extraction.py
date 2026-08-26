"""SoAI - Managed asset archive extraction dispatch [backend/core/bootstrap/managed_archive_extraction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Collection

from core.archives.tar_extraction import safe_tar_extractall
from core.archives.zip_extraction import safe_zip_extractall
from core.errors.exceptions import StateError
from core.hardware.protocols_storage import StorageManagerProtocol
from core.runtime.platform import get_runtime_platform

__all__ = (
    "detect_managed_asset_platform_id",
    "extract_managed_asset_archive",
)


def detect_managed_asset_platform_id(
    *,
    managed_asset: str,
    supported_platform_ids: Collection[str],
) -> str:
    runtime_platform = get_runtime_platform()
    platform_id = runtime_platform.platform_id
    if platform_id is None:
        raise StateError(
            f"Unsupported platform for managed {managed_asset}: system={runtime_platform.os_name!r}, arch={runtime_platform.architecture!r}",
        )
    if platform_id not in supported_platform_ids:
        raise StateError(
            f"Unsupported platform for managed {managed_asset}: platform_id={platform_id!r}",
        )
    return platform_id


def extract_managed_asset_archive(
    download_path: str,
    *,
    extracted_root: str,
    archive_format: str,
    managed_asset: str,
    reservation_provider: StorageManagerProtocol,
) -> None:
    if archive_format == "zip":
        safe_zip_extractall(
            download_path,
            extracted_root,
            reservation_provider=reservation_provider,
        )
        return
    if archive_format == "tar.gz":
        safe_tar_extractall(
            download_path,
            extracted_root,
            reservation_provider=reservation_provider,
        )
        return
    raise StateError(f"Unsupported managed {managed_asset} archive format.")
