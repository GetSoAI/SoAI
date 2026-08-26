"""SoAI - Browser adblock snapshot and cache sources [backend/core/browser_adblock/source.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import gzip
import hashlib
import os
import re
import shutil
from dataclasses import dataclass
from importlib import resources
from typing import TYPE_CHECKING

from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import ValidationError
from core.files.locking import guarded_file_lock
from core.files.temp_files import create_persistent_staging_directory
from core.filesystem.file_sync import flush_and_fsync_file
from core.filesystem.open_files import open_binary, open_text
from core.hardware.disk_reservation_records import DiskSpaceReservationRequest
from core.hardware.reservation_claims import claim_reserved_write
from core.meta.paths import join_data_abs
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_dict
from core.timing.epoch import epoch_seconds_float
from core.validation.numbers import coerce_float_from_json

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.types.json import JSONDict

__all__ = (
    "EasyListCachePaths",
    "EasyListSnapshot",
    "compute_next_refresh_unix",
    "load_cached_snapshot",
    "load_packaged_snapshot",
    "parse_expires_seconds",
    "resolve_cache_paths",
    "write_cached_snapshot",
)

DEFAULT_REFRESH_SECONDS = 345_600
MAX_CACHE_UNCOMPRESSED_BYTES = 16 * MIB_BYTES


@dataclass(frozen=True, slots=True)
class EasyListCachePaths:
    cache_dir: str
    cache_file_path: str
    metadata_file_path: str
    lock_file_path: str


@dataclass(frozen=True, slots=True)
class EasyListSnapshot:
    raw_text: str
    source_name: str
    fetched_at_unix: float
    next_refresh_unix: float


def _compress_cached_snapshot(raw_text: str) -> bytes:
    return gzip.compress(raw_text.encode("utf-8"))


def _read_cached_raw_text(cache_file_path: str) -> str:
    with gzip.open(cache_file_path, "rb") as cache_file:
        raw_bytes = cache_file.read(MAX_CACHE_UNCOMPRESSED_BYTES + 1)
    if len(raw_bytes) > MAX_CACHE_UNCOMPRESSED_BYTES:
        raise ValidationError("EasyList cache exceeds the maximum uncompressed size.")
    return raw_bytes.decode("utf-8", errors="replace")


def _sha256_text(raw_text: str) -> str:
    return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()


def _require_metadata_match(metadata: JSONDict, raw_text: str) -> None:
    expected_size = metadata.get("raw_size_bytes")
    raw_bytes = raw_text.encode("utf-8")
    if expected_size != len(raw_bytes):
        raise ValidationError("EasyList cache metadata size does not match cached content.")
    expected_hash = metadata.get("raw_sha256")
    if expected_hash != hashlib.sha256(raw_bytes).hexdigest():
        raise ValidationError("EasyList cache metadata hash does not match cached content.")


def _write_cached_snapshot_file(cache_temp_path: str, compressed_bytes: bytes) -> None:
    with open_binary(cache_temp_path, mode="wb") as cache_handle:
        cache_handle.write(compressed_bytes)
        flush_and_fsync_file(cache_handle)


def _write_cached_snapshot_metadata(
    metadata_temp_path: str,
    metadata_text: str,
) -> None:
    with open_text(metadata_temp_path, mode="w", encoding="utf-8") as metadata_file:
        metadata_file.write(metadata_text)
        flush_and_fsync_file(metadata_file)


def resolve_cache_paths(base_path: str) -> EasyListCachePaths:
    if not base_path.strip():
        raise ValidationError(
            "SYSTEM.PATHS.BASE must be configured for browser adblock cache paths.",
        )
    cache_dir = join_data_abs(base_path, "cache", "browser_adblock")
    return EasyListCachePaths(
        cache_dir=cache_dir,
        cache_file_path=os.path.join(cache_dir, "easylist.txt.gz"),
        metadata_file_path=os.path.join(cache_dir, "easylist.json"),
        lock_file_path=os.path.join(cache_dir, "easylist.lock"),
    )


def load_packaged_snapshot() -> EasyListSnapshot:
    package = resources.files("core.browser_adblock.assets")
    raw_bytes = package.joinpath("easylist.txt.gz").read_bytes()
    raw_text = gzip.decompress(raw_bytes).decode("utf-8", errors="replace")
    fetched_at_unix = 0.0
    next_refresh_unix = compute_next_refresh_unix(raw_text, fetched_at_unix=fetched_at_unix)
    return EasyListSnapshot(
        raw_text=raw_text,
        source_name="packaged_snapshot",
        fetched_at_unix=fetched_at_unix,
        next_refresh_unix=next_refresh_unix,
    )


def load_cached_snapshot(paths: EasyListCachePaths) -> EasyListSnapshot | None:
    if not os.path.exists(paths.cache_file_path) or not os.path.exists(paths.metadata_file_path):
        return None
    try:
        with open_text(paths.metadata_file_path, encoding="utf-8") as metadata_file:
            metadata = parse_json_dict(metadata_file.read(), field="adblock cache metadata")
    except (OSError, ValidationError):
        return None
    raw_text = _read_cached_raw_text(paths.cache_file_path)
    _require_metadata_match(metadata, raw_text)
    fetched_at_unix_value = coerce_float_from_json(metadata.get("fetched_at_unix"), default=0.0)
    fetched_at_unix = 0.0 if fetched_at_unix_value is None else fetched_at_unix_value
    default_next_refresh = compute_next_refresh_unix(raw_text, fetched_at_unix=fetched_at_unix)
    next_refresh_unix_value = coerce_float_from_json(
        metadata.get("next_refresh_unix"),
        default=default_next_refresh,
    )
    next_refresh_unix = (
        default_next_refresh if next_refresh_unix_value is None else next_refresh_unix_value
    )
    return EasyListSnapshot(
        raw_text=raw_text,
        source_name=str(metadata.get("source_name", "cache")),
        fetched_at_unix=fetched_at_unix,
        next_refresh_unix=next_refresh_unix,
    )


def compute_next_refresh_unix(raw_text: str, *, fetched_at_unix: float) -> float:
    expires_seconds = parse_expires_seconds(raw_text)
    return float(fetched_at_unix) + float(expires_seconds)


def parse_expires_seconds(raw_text: str) -> int:
    expires_pattern = re.compile(
        r"!\s*expires\s*:\s*(\d+)\s*(hour|hours|day|days)",
        re.IGNORECASE,
    )
    for line in raw_text.splitlines():
        match = expires_pattern.search(line)
        if match is None:
            continue
        amount = int(match.group(1))
        unit = match.group(2).lower()
        if "hour" in unit:
            return max(3600, amount * 3600)
        return max(3600, amount * 24 * 3600)
    return DEFAULT_REFRESH_SECONDS


def write_cached_snapshot(
    paths: EasyListCachePaths,
    *,
    raw_text: str,
    source_name: str,
    fetched_at_unix: float,
    storage_manager: StorageManagerProtocol,
) -> EasyListSnapshot:
    os.makedirs(paths.cache_dir, exist_ok=True)
    next_refresh_unix = compute_next_refresh_unix(raw_text, fetched_at_unix=fetched_at_unix)
    raw_bytes = raw_text.encode("utf-8")
    metadata: dict[str, float | int | str] = {
        "fetched_at_unix": float(fetched_at_unix),
        "next_refresh_unix": float(next_refresh_unix),
        "raw_sha256": _sha256_text(raw_text),
        "raw_size_bytes": len(raw_bytes),
        "source_name": source_name,
        "updated_at_unix": epoch_seconds_float(),
    }
    compressed_bytes = _compress_cached_snapshot(raw_text)
    metadata_text = serialize_json_compact_stable_strict(metadata)
    cache_bytes = len(compressed_bytes)
    metadata_bytes = len(metadata_text.encode("utf-8"))
    temp_dir = create_persistent_staging_directory(
        directory=paths.cache_dir,
        prefix="browser_adblock_",
    )
    try:
        with guarded_file_lock(
            paths.lock_file_path,
            timeout=0.0,
            on_timeout=ValidationError("EasyList cache write is already in progress."),
        ):
            cache_temp_path = os.path.join(temp_dir, "easylist.txt.gz")
            metadata_temp_path = os.path.join(temp_dir, "easylist.json")
            with storage_manager.reserve_many_disk_spaces(
                requests=(
                    DiskSpaceReservationRequest(
                        path=cache_temp_path,
                        required_bytes=cache_bytes,
                        operation="browser_adblock.cache.write",
                        details={
                            "purpose": "easylist_gzip_cache",
                            "source_name": source_name,
                        },
                    ),
                    DiskSpaceReservationRequest(
                        path=metadata_temp_path,
                        required_bytes=metadata_bytes,
                        operation="browser_adblock.cache.write",
                        details={
                            "purpose": "easylist_metadata_cache",
                            "source_name": source_name,
                        },
                    ),
                ),
            ) as reservation:
                with claim_reserved_write(reservation, size_bytes=cache_bytes):
                    _write_cached_snapshot_file(cache_temp_path, compressed_bytes)
                with claim_reserved_write(reservation, size_bytes=metadata_bytes):
                    _write_cached_snapshot_metadata(metadata_temp_path, metadata_text)
                os.replace(cache_temp_path, paths.cache_file_path)
                os.replace(metadata_temp_path, paths.metadata_file_path)
    finally:
        if os.path.lexists(temp_dir):
            shutil.rmtree(temp_dir)
    return EasyListSnapshot(
        raw_text=raw_text,
        source_name=source_name,
        fetched_at_unix=fetched_at_unix,
        next_refresh_unix=next_refresh_unix,
    )
