"""SoAI - Bootstrap archive extraction and SHA-256-verified downloads [backend/core/bootstrap/archive_extraction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
import tempfile

from core.bootstrap.download_stream import download_http_binary_to_path
from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import StateError
from core.filesystem.open_files import open_binary
from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = ("download_and_verify_sha256",)


def download_and_verify_sha256(
    url: str,
    *,
    expected_sha256: str,
    user_agent: str,
    reservation_provider: StorageManagerProtocol,
    prefix: str = "soai-bootstrap-download-",
    timeout_sec: float = 120.0,
    max_bytes: int | None = None,
) -> str:
    expected = expected_sha256.strip().lower()
    if not expected or any(ch not in "0123456789abcdef" for ch in expected) or len(expected) != 64:
        raise StateError(f"Invalid expected sha256 for bootstrap download from {url}.")
    with tempfile.NamedTemporaryFile(delete=False, prefix=prefix, suffix=".tmp") as temp_handle:
        temp_path = temp_handle.name
    success = False
    try:
        download_http_binary_to_path(
            url,
            target_path=temp_path,
            user_agent=user_agent,
            timeout_sec=timeout_sec,
            max_bytes=max_bytes,
            reservation_provider=reservation_provider,
        )
        digest = hashlib.sha256()
        with open_binary(temp_path, mode="rb") as digest_handle:
            for chunk in iter(lambda: digest_handle.read(MIB_BYTES), b""):
                digest.update(chunk)
        actual = digest.hexdigest().lower()
        if actual != expected:
            raise StateError(
                f"Bootstrap download sha256 mismatch for {url}: expected {expected}, got {actual}.",
            )
        success = True
        return temp_path
    finally:
        if not success and os.path.exists(temp_path):
            os.unlink(temp_path)
