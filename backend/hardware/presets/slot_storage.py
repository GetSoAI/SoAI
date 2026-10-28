"""SoAI - GPU slot storage and normalization [backend/hardware/presets/slot_storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import io
import os
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError
from core.filesystem.atomic_binary_writes import atomic_write_binary, atomic_write_binary_content
from core.filesystem.atomic_write_primitives import fsync_directory
from core.filesystem.open_files import open_binary
from core.hardware.gpu_control_types import (
    GPUSlotReadError,
    GPUSlotReadFailure,
    GPUSlotReadResult,
    GPUSlotReadState,
    GPUSlotWriteError,
    GPUSlotWriteFailure,
)
from core.logging.protocols import LoggerProtocol
from core.serialization.json import serialize_json_pretty_sorted_strict
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from hardware.control.profiles import GPU_SLOT_FILE_VERSION
from hardware.presets.slot_control_state import (
    is_slots_payload_empty,
    require_empty_payload_deletion_authority,
)
from hardware.presets.slot_format import decode_gpu_slot_payload, validate_gpu_slot_payload

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "GpuSlotStorageManager",
    "GpuSlotStorageManagerDependencies",
    "serialize_gpu_slot_write_bytes",
)

LOGGER_NAME = "SoAI.hardware.presets.slot_storage"
OPERATION = "gpu_slot_storage_manager.read_payload"


def serialize_gpu_slot_write_bytes(payload: JSONDict) -> bytes:
    content = serialize_json_pretty_sorted_strict(payload)
    return content.replace("\n", os.linesep).encode("utf-8")


@dataclass(frozen=True, slots=True)
class GpuSlotStorageManagerDependencies:
    path: str
    logger: LoggerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="GpuSlotStorageManagerDependencies",
            logger=self.logger,
            path=self.path,
        )


class GpuSlotStorageManager:
    def __init__(self, deps: GpuSlotStorageManagerDependencies) -> None:
        self._path = deps.path
        self.lock = threading.RLock()
        self.logger = deps.logger

    def read_payload(self) -> GPUSlotReadResult:
        with self.lock:
            try:
                with open_binary(self._path) as handle:
                    raw = handle.read()
            except FileNotFoundError as exception:
                if os.path.lexists(self._path):
                    raise GPUSlotReadError(GPUSlotReadFailure.UNAVAILABLE) from exception
                return GPUSlotReadResult(
                    payload={"version": GPU_SLOT_FILE_VERSION, "devices": {}, "recovery": {}},
                    state=GPUSlotReadState.ABSENT,
                    source_format=None,
                    revision=None,
                    migration_required=False,
                )
            except PermissionError as exception:
                raise GPUSlotReadError(GPUSlotReadFailure.PERMISSION_DENIED) from exception
            except OSError as exception:
                raise GPUSlotReadError(GPUSlotReadFailure.UNAVAILABLE) from exception
            return decode_gpu_slot_payload(raw)

    def write_payload(
        self,
        payload: JSONDict,
        *,
        expected_read: GPUSlotReadResult | None = None,
    ) -> None:
        with self.lock:
            try:
                if payload.get("version") != GPU_SLOT_FILE_VERSION:
                    raise ValidationError("GPU slot writes require the current format.")
                validate_gpu_slot_payload(payload)
                content = serialize_gpu_slot_write_bytes(payload)
                decode_gpu_slot_payload(content)
            except (GPUSlotReadError, ValidationError, ValueError) as exception:
                raise GPUSlotWriteError(GPUSlotWriteFailure.INVALID_PAYLOAD) from exception
            current_read = self.read_payload()
            if expected_read is not None and current_read.revision != expected_read.revision:
                raise GPUSlotWriteError(GPUSlotWriteFailure.REVISION_CONFLICT)

            try:
                current_devices = current_read.payload.get("devices", {})
                next_devices = payload.get("devices", {})
                removed_aliases = (
                    isinstance(current_devices, dict)
                    and isinstance(next_devices, dict)
                    and bool(set(current_devices) - set(next_devices))
                )
                if (
                    current_read.source_format == 1
                    or removed_aliases
                    or payload.get("alias_history") != current_read.payload.get("alias_history")
                ):
                    self._preserve_original(current_read)
                    if self.read_payload().revision != current_read.revision:
                        raise GPUSlotWriteError(GPUSlotWriteFailure.REVISION_CONFLICT)
                atomic_write_binary_content(self._path, content)
            except PermissionError as exception:
                raise GPUSlotWriteError(GPUSlotWriteFailure.PERMISSION_DENIED) from exception
            except OSError as exception:
                raise GPUSlotWriteError(GPUSlotWriteFailure.UNAVAILABLE) from exception
            try:
                fsync_directory(os.path.dirname(self._path) or ".", strict=True)
            except OSError as exception:
                raise GPUSlotWriteError(GPUSlotWriteFailure.PERSISTENCE_UNCERTAIN) from exception

    def _preserve_original(self, read: GPUSlotReadResult) -> None:
        if read.state == GPUSlotReadState.ABSENT:
            return
        with open_binary(self._path) as handle:
            raw = handle.read()
        if hashlib.sha256(raw).hexdigest() != read.revision:
            raise GPUSlotWriteError(GPUSlotWriteFailure.REVISION_CONFLICT)
        backup_path = f"{self._path}.before-{read.revision}.json"

        def write_original(handle: io.BufferedIOBase) -> None:
            handle.write(raw)

        try:
            atomic_write_binary(
                backup_path,
                write_original,
                exclusive=True,
                file_mode=0o600,
                fsync_parent_directory=True,
            )
        except FileExistsError as exception:
            with open_binary(backup_path, mode="r+b" if os.name == "nt" else "rb") as preserved:
                if preserved.read() != raw:
                    raise GPUSlotWriteError(
                        GPUSlotWriteFailure.PERSISTENCE_UNCERTAIN
                    ) from exception
                os.fsync(preserved.fileno())
            fsync_directory(os.path.dirname(backup_path) or ".", strict=True)

    def remove_empty_payload(self, payload: JSONDict, *, expected_read: GPUSlotReadResult) -> None:
        with self.lock:
            try:
                records = validate_gpu_slot_payload(payload)
                if records or not is_slots_payload_empty(payload):
                    raise ValidationError("GPU deletion requires complete empty authority.")
            except (ValidationError, ValueError) as exception:
                raise GPUSlotWriteError(GPUSlotWriteFailure.INVALID_PAYLOAD) from exception
            current = self.read_payload()
            if current.revision != expected_read.revision or current.recovery_records:
                raise GPUSlotWriteError(GPUSlotWriteFailure.REVISION_CONFLICT)
            try:
                if current.state != GPUSlotReadState.ABSENT:
                    require_empty_payload_deletion_authority(payload, current.payload)
            except ValidationError as exception:
                raise GPUSlotWriteError(GPUSlotWriteFailure.INVALID_PAYLOAD) from exception
            try:
                if current.state != GPUSlotReadState.ABSENT:
                    os.unlink(self._path)
            except PermissionError as exception:
                raise GPUSlotWriteError(GPUSlotWriteFailure.PERMISSION_DENIED) from exception
            except OSError as exception:
                raise GPUSlotWriteError(GPUSlotWriteFailure.UNAVAILABLE) from exception
            try:
                fsync_directory(os.path.dirname(self._path) or ".", strict=True)
            except OSError as exception:
                raise GPUSlotWriteError(GPUSlotWriteFailure.PERSISTENCE_UNCERTAIN) from exception
            try:
                after = self.read_payload()
            except GPUSlotReadError as exception:
                raise GPUSlotWriteError(GPUSlotWriteFailure.PERSISTENCE_UNCERTAIN) from exception
            if after.state != GPUSlotReadState.ABSENT:
                raise GPUSlotWriteError(GPUSlotWriteFailure.PERSISTENCE_UNCERTAIN)

    def synchronize_revision(self, *, expected_revision: str) -> None:
        require_canonical_sha256_hexdigest(expected_revision, label="GPU synchronization revision")
        with self.lock:
            try:
                with open_binary(self._path, mode="r+b" if os.name == "nt" else "rb") as handle:
                    read = decode_gpu_slot_payload(handle.read())
                    if read.revision != expected_revision:
                        raise GPUSlotWriteError(GPUSlotWriteFailure.REVISION_CONFLICT)
                    os.fsync(handle.fileno())
                fsync_directory(os.path.dirname(self._path) or ".", strict=True)
            except FileNotFoundError as exception:
                raise GPUSlotWriteError(GPUSlotWriteFailure.UNAVAILABLE) from exception
            except PermissionError as exception:
                raise GPUSlotWriteError(GPUSlotWriteFailure.PERMISSION_DENIED) from exception
            except OSError as exception:
                raise GPUSlotWriteError(GPUSlotWriteFailure.PERSISTENCE_UNCERTAIN) from exception
            if self.read_payload().revision != expected_revision:
                raise GPUSlotWriteError(GPUSlotWriteFailure.REVISION_CONFLICT)
