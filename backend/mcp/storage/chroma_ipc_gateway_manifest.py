"""SoAI - Chroma IPC shard manifest helpers [backend/mcp/storage/chroma_ipc_gateway_manifest.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConfigurationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.atomic_writes import atomic_write_text_content
from core.filesystem.open_files import open_text
from core.hardware.protocols_storage import StorageManagerProtocol
from core.hardware.reservation_claims import claim_reserved_write
from core.logging.trace import get_logger
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_value
from core.validation.numbers import coerce_int_from_json

__all__ = ("ensure_shard_manifest",)

LOGGER_NAME = "SoAI.mcp.storage.chroma_ipc_gateway_manifest"
MANIFEST_FILENAME = ".soai_chroma_shards.json"
OPERATION_MCP_STORAGE_CHROMA_IPC_MANIFEST_READ = "mcp.storage.chroma_ipc.manifest.read"
OPERATION_MCP_STORAGE_CHROMA_IPC_MANIFEST_WRITE = "mcp.storage.chroma_ipc.manifest.write"


def ensure_shard_manifest(
    base_dir: str,
    shard_count: int,
    storage_manager: StorageManagerProtocol,
) -> None:
    manifest_path = os.path.join(base_dir, MANIFEST_FILENAME)
    payload = {"shards": int(shard_count)}
    if os.path.exists(manifest_path):
        try:
            with open_text(
                manifest_path,
                mode="r",
                encoding="utf-8",
                errors="strict",
            ) as handle:
                existing = parse_json_value(handle.read())
            if isinstance(existing, dict):
                existing_shards_value = coerce_int_from_json(
                    existing.get("shards"),
                    default=0,
                    allow_bool=False,
                    parse_float_strings=True,
                    round_float_strings=True,
                )
                existing_shards = 0 if existing_shards_value is None else existing_shards_value
                if existing_shards == int(shard_count):
                    return
                raise ConfigurationError(
                    "Chroma shard count mismatch; refusing startup.",
                    operation="mcp.storage.chroma_ipc.manifest.mismatch",
                    details={
                        "existing_shards": int(existing_shards),
                        "configured_shards": int(shard_count),
                        "manifest_path": str(manifest_path),
                    },
                )
        except RECOVERABLE_EXCEPTIONS as exception:
            logger = get_logger(LOGGER_NAME)
            error = coerce_to_soai_error(
                exception,
                operation=OPERATION_MCP_STORAGE_CHROMA_IPC_MANIFEST_READ,
                details={"manifest_path": str(manifest_path)},
            )
            log_exception(
                logger,
                error,
                message="Failed to read Chroma shard manifest; refusing startup.",
                operation=OPERATION_MCP_STORAGE_CHROMA_IPC_MANIFEST_READ,
                details={"manifest_path": str(manifest_path)},
                level="warning",
            )
            raise ConfigurationError(
                "Failed to read Chroma shard manifest; refusing startup.",
                operation=OPERATION_MCP_STORAGE_CHROMA_IPC_MANIFEST_READ,
                cause=exception,
            ) from exception
    content = serialize_json_compact_stable_strict(payload, ensure_ascii=False)
    required_bytes = len(content.encode("utf-8"))
    with (
        storage_manager.reserve_disk_space(
            path=manifest_path,
            required_bytes=required_bytes,
            operation=OPERATION_MCP_STORAGE_CHROMA_IPC_MANIFEST_WRITE,
            details={"manifest_path": manifest_path, "required_bytes": required_bytes},
        ) as reservation,
        claim_reserved_write(reservation, size_bytes=required_bytes),
    ):
        atomic_write_text_content(
            manifest_path,
            content,
            encoding="utf-8",
            errors="strict",
        )
