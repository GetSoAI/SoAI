"""SoAI - Media proxy disk cache helpers [backend/webui/manager/media_preview_proxy_cache.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import SoAIError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.atomic_writes import atomic_write_text_content
from core.filesystem.open_files import open_text
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.serialization.json import serialize_json_pretty_sorted
from core.serialization.json_parsing import parse_json_value
from core.timing.epoch import epoch_seconds_float
from core.types.json import JSONDict, is_json_dict
from webui.manager.media_preview_proxy_cache_pruning import prune_cache_dir

__all__ = (
    "build_cache_paths",
    "build_cache_temp_path",
    "build_proxy_cache_key",
    "ensure_cache_dir_exists",
    "promote_cache_file_with_metadata_text",
    "prune_cache_dir",
    "remove_temp_file_if_present",
    "serialize_cache_metadata_text",
    "touch_cache_file",
    "try_read_cache_metadata",
    "write_cache_metadata_atomic",
)

LOGGER_NAME = "SoAI.webui.manager.media_preview_proxy_cache"
OPERATION_READ = "webui.media.proxy.cache.read"
OPERATION_WRITE = "webui.media.proxy.cache.write"
CACHE_METADATA_WRITE_EXCEPTIONS: tuple[type[Exception], ...] = (
    OSError,
    SoAIError,
    *RECOVERABLE_EXCEPTIONS,
)


async def remove_temp_file_if_present(
    *,
    logger: LoggerProtocol,
    operation: str,
    temp_path: str,
    message: str,
) -> None:
    if not await asyncio.to_thread(os.path.exists, temp_path):
        return
    try:
        await asyncio.to_thread(os.remove, temp_path)
    except OSError as cleanup_exception:
        log_handled_exception(
            logger,
            cleanup_exception,
            message=message,
            operation=operation,
            details={"path": temp_path},
            level="debug",
        )


def build_proxy_cache_key(url: str) -> str:
    normalized = str(url or "").strip()
    if not normalized:
        raise ValidationError("Cache key URL must be provided.")
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return digest


def build_cache_paths(cache_dir: str, key: str) -> tuple[str, str]:
    normalized_dir = str(cache_dir or "").strip()
    if not normalized_dir:
        raise ValidationError("Cache directory must be provided.")
    normalized_key = str(key or "").strip()
    if not normalized_key:
        raise ValidationError("Cache key must be provided.")
    data_path = os.path.join(normalized_dir, f"{normalized_key}.bin")
    meta_path = os.path.join(normalized_dir, f"{normalized_key}.json")
    return (data_path, meta_path)


def build_cache_temp_path(cache_dir: str, key: str) -> str:
    normalized_dir = str(cache_dir or "").strip()
    normalized_key = str(key or "").strip()
    if not normalized_dir or not normalized_key:
        raise ValidationError("Cache directory and key must be provided.")
    token = uuid.uuid4().hex
    return os.path.join(normalized_dir, f"{normalized_key}.tmp.{token}.partial")


async def ensure_cache_dir_exists(cache_dir: str) -> None:
    if not cache_dir:
        raise ValidationError("Cache directory must be provided.")
    await asyncio.to_thread(os.makedirs, cache_dir, exist_ok=True)


async def promote_cache_file_with_metadata_text(
    *,
    temp_path: str,
    data_path: str,
    meta_path: str,
    metadata_text: str,
) -> None:
    await asyncio.to_thread(os.replace, temp_path, data_path)
    try:
        await write_cache_metadata_text_atomic(meta_path, metadata_text)
    except CACHE_METADATA_WRITE_EXCEPTIONS:
        try:
            await asyncio.to_thread(_remove_path_if_exists, data_path)
        except OSError as cleanup_exception:
            log_handled_exception(
                get_logger(LOGGER_NAME),
                cleanup_exception,
                message="Failed to remove media proxy cache data after metadata write failure.",
                operation=OPERATION_WRITE,
                details={"path": data_path},
                level="warning",
            )
        raise


async def try_read_cache_metadata(meta_path: str) -> JSONDict | None:
    logger = get_logger(LOGGER_NAME)
    try:
        raw = await asyncio.to_thread(_read_text_file, meta_path)
    except FileNotFoundError:
        return None
    except CACHE_METADATA_WRITE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to read media proxy cache metadata",
            operation=OPERATION_READ,
            level="warning",
        )
        return None
    try:
        parsed = parse_json_value(raw)
    except (ValidationError, ValueError) as exception:
        log_exception(
            logger,
            exception,
            message="Invalid media proxy cache metadata JSON",
            operation=OPERATION_READ,
            level="warning",
        )
        return None
    if not is_json_dict(parsed):
        return None
    return dict(parsed)


def serialize_cache_metadata_text(payload: JSONDict) -> str:
    return serialize_json_pretty_sorted(payload, ensure_ascii=True)


def _read_text_file(path: str) -> str:
    with open_text(path, mode="r", encoding="utf-8") as handle:
        return handle.read()


def _remove_path_if_exists(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)


async def write_cache_metadata_atomic(meta_path: str, payload: JSONDict) -> None:
    await write_cache_metadata_text_atomic(meta_path, serialize_cache_metadata_text(payload))


async def write_cache_metadata_text_atomic(meta_path: str, text: str) -> None:
    logger = get_logger(LOGGER_NAME)
    if not meta_path:
        raise ValidationError("Metadata path must be provided.")
    directory = os.path.dirname(meta_path)
    if directory:
        await asyncio.to_thread(os.makedirs, directory, exist_ok=True)
    try:
        await asyncio.to_thread(
            atomic_write_text_content,
            meta_path,
            text,
            ensure_parent=False,
            fsync=True,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to write media proxy cache metadata",
            operation=OPERATION_WRITE,
            level="warning",
        )
        raise


async def touch_cache_file(data_path: str) -> None:
    if not data_path:
        return
    now = epoch_seconds_float()
    try:
        await asyncio.to_thread(os.utime, data_path, (now, now))
    except OSError:
        return
