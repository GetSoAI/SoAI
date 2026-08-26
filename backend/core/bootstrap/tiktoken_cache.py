"""SoAI - Managed tiktoken encoding cache [backend/core/bootstrap/tiktoken_cache.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass

from core.bootstrap.disk_reservation_provider import create_bootstrap_disk_reservation_provider
from core.bootstrap.download_stream import download_http_binary_to_path
from core.bootstrap.files import compute_sha256
from core.bootstrap.lock import acquire_interprocess_lock
from core.errors.exceptions import StateError

__all__ = (
    "TiktokenCacheAsset",
    "ensure_tiktoken_cache_installed",
    "find_invalid_tiktoken_cache_assets",
    "list_tiktoken_cache_assets",
)


@dataclass(frozen=True, slots=True)
class TiktokenCacheAsset:
    url: str
    sha256: str

    @property
    def cache_key(self) -> str:
        return hashlib.new(
            "sha1",
            self.url.encode("utf-8"),
            usedforsecurity=False,
        ).hexdigest()


def list_tiktoken_cache_assets() -> tuple[TiktokenCacheAsset, ...]:
    return (
        TiktokenCacheAsset(
            url="https://openaipublic.blob.core.windows.net/gpt-2/encodings/main/vocab.bpe",
            sha256=(
                "1ce16647"
                "73c50f3e"
                "0cc88426"
                "19a93edc"
                "4624525b"
                "728b188a"
                "9e0be33b"
                "7726adc5"
            ),
        ),
        TiktokenCacheAsset(
            url="https://openaipublic.blob.core.windows.net/gpt-2/encodings/main/encoder.json",
            sha256=(
                "19613966"
                "8be63f3b"
                "5d657442"
                "7317ae82"
                "f612a97c"
                "5d1cdaf3"
                "6ed2256d"
                "bf636783"
            ),
        ),
        TiktokenCacheAsset(
            url="https://openaipublic.blob.core.windows.net/encodings/r50k_base.tiktoken",
            sha256=(
                "306cd27f"
                "03c1a714"
                "eca7108e"
                "03d66b7d"
                "c042abe8"
                "c258b44c"
                "199a7ed9"
                "838dd930"
            ),
        ),
        TiktokenCacheAsset(
            url="https://openaipublic.blob.core.windows.net/encodings/p50k_base.tiktoken",
            sha256=(
                "94b5ca7d"
                "ff4d0076"
                "7bc256fd"
                "d1b27e5b"
                "17361d7b"
                "8a5f9685"
                "47f9f23e"
                "b70d2069"
            ),
        ),
        TiktokenCacheAsset(
            url="https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken",
            sha256=(
                "223921b7"
                "6ee99bde"
                "995b7ff7"
                "38513eef"
                "100fb51d"
                "18c93597"
                "a113bcff"
                "e865b2a7"
            ),
        ),
        TiktokenCacheAsset(
            url="https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken",
            sha256=(
                "446a9538"
                "cb6c348e"
                "3516120d"
                "7c08b09f"
                "57c36495"
                "e2acfffe"
                "59a5bf8b"
                "0cfb1a2d"
            ),
        ),
    )


def find_invalid_tiktoken_cache_assets(cache_path: str) -> list[TiktokenCacheAsset]:
    invalid: list[TiktokenCacheAsset] = []
    for asset in list_tiktoken_cache_assets():
        asset_path = os.path.join(cache_path, asset.cache_key)
        try:
            matches = os.path.isfile(asset_path) and compute_sha256(asset_path) == asset.sha256
        except OSError:
            matches = False
        if not matches:
            invalid.append(asset)
    return invalid


def ensure_tiktoken_cache_installed(
    repo_root_path: str,
    cache_path: str,
    locks_path: str,
) -> None:
    lock_path = os.path.join(locks_path, "soai.tiktoken.lock")
    with acquire_interprocess_lock(lock_path, timeout_sec=1800.0):
        invalid = find_invalid_tiktoken_cache_assets(cache_path)
        if not invalid:
            return
        os.makedirs(cache_path, exist_ok=True)
        reservation_provider = create_bootstrap_disk_reservation_provider(repo_root_path)
        for asset in invalid:
            descriptor, staging_path = tempfile.mkstemp(
                dir=cache_path,
                prefix=".tiktoken-",
                suffix=".tmp",
            )
            os.close(descriptor)
            try:
                download_http_binary_to_path(
                    asset.url,
                    target_path=staging_path,
                    user_agent="SoAI/managed-tiktoken",
                    timeout_sec=300.0,
                    reservation_provider=reservation_provider,
                    max_bytes=67_108_864,
                    require_https_final_url=True,
                )
                if compute_sha256(staging_path) != asset.sha256:
                    raise StateError("Managed tiktoken encoding checksum verification failed.")
                os.replace(staging_path, os.path.join(cache_path, asset.cache_key))
            finally:
                if os.path.exists(staging_path):
                    os.unlink(staging_path)
