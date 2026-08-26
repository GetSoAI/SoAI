"""SoAI - Managed asset installation helpers [backend/core/bootstrap/managed_asset_installation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil

from core.bootstrap.archive_extraction import download_and_verify_sha256
from core.bootstrap.managed_archive_extraction import extract_managed_asset_archive
from core.errors.exceptions import StateError
from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = ("install_managed_asset_archive",)


def install_managed_asset_archive(
    *,
    install_dir: str,
    managed_asset: str,
    download_url: str,
    expected_sha256: str,
    user_agent: str,
    archive_format: str,
    reservation_provider: StorageManagerProtocol,
    download_prefix: str | None = None,
    max_download_bytes: int | None = None,
) -> str:
    if os.path.isdir(install_dir):
        try:
            shutil.rmtree(install_dir)
        except OSError as exception:
            raise StateError(
                f"Failed to remove existing managed {managed_asset} directory.",
            ) from exception
    os.makedirs(install_dir, exist_ok=True)

    download_path = download_and_verify_sha256(
        download_url,
        expected_sha256=expected_sha256,
        user_agent=user_agent,
        prefix=download_prefix if download_prefix is not None else "",
        max_bytes=max_download_bytes,
        reservation_provider=reservation_provider,
    )
    extracted_root = os.path.join(install_dir, "runtime")
    os.makedirs(extracted_root, exist_ok=True)
    try:
        extract_managed_asset_archive(
            download_path,
            extracted_root=extracted_root,
            archive_format=archive_format,
            managed_asset=managed_asset,
            reservation_provider=reservation_provider,
        )
    finally:
        if os.path.exists(download_path):
            os.unlink(download_path)
    return extracted_root
