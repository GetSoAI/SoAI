"""SoAI - Disk reservation ledger file storage [backend/core/hardware/disk_reservation_store.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from typing import TYPE_CHECKING, TypedDict

from core.errors.exceptions import StateError, ValidationError
from core.files.lock_acquisition_retry import retrying_guarded_file_lock
from core.filesystem.atomic_writes import atomic_write_text_content
from core.filesystem.open_files import open_text
from core.hardware.disk_reservation_records import (
    DiskReservationPayload,
    DiskReservationRecord,
    is_disk_reservation_record_stale,
    parse_disk_reservation_record,
)
from core.serialization.json import serialize_json_pretty_sorted_strict
from core.serialization.json_parsing import parse_json_dict
from core.types.json_value import filter_json_mapping_strict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("DiskReservationFileStore",)

SCHEMA_VERSION = 1
_LOCK_OPERATION = "core.hardware.disk_reservation_store.acquire_lock"
_LOCK_EXHAUSTED_MESSAGE = "Timed out waiting for the disk reservation ledger lock."


class _DiskReservationLedgerFields(TypedDict):
    schema_version: int
    reservations: list[DiskReservationPayload]


class DiskReservationFileStore:
    def __init__(self, *, ledger_path: str, lock_path: str, lock_timeout_sec: float) -> None:
        self.ledger_path = os.path.abspath(ledger_path)
        self.lock_path = os.path.abspath(lock_path)
        self.lock_timeout_sec = float(lock_timeout_sec)
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.lock_path), exist_ok=True)

    @contextmanager
    def locked(self) -> Generator[None]:
        with retrying_guarded_file_lock(
            self.lock_path,
            timeout_seconds=self.lock_timeout_sec,
            operation=_LOCK_OPERATION,
            exhausted_message=_LOCK_EXHAUSTED_MESSAGE,
        ):
            yield

    def read_active_records_locked(self) -> list[DiskReservationRecord]:
        records = self.read_records_locked()
        return [record for record in records if not is_disk_reservation_record_stale(record)]

    def read_records_locked(self) -> list[DiskReservationRecord]:
        if not os.path.exists(self.ledger_path):
            return []
        payload = self._read_payload_locked()
        version = payload.get("schema_version")
        if version != SCHEMA_VERSION:
            raise StateError(
                "Disk reservation ledger schema version is invalid.",
                details={"path": self.ledger_path, "schema_version": version},
            )
        reservations_value = payload.get("reservations")
        if not isinstance(reservations_value, list):
            raise StateError(
                "Disk reservation ledger reservations must be an array.",
                details={"path": self.ledger_path},
            )
        return [_parse_record_entry(entry) for entry in reservations_value]

    def write_records_locked(self, records: Sequence[DiskReservationRecord]) -> None:
        payload: _DiskReservationLedgerFields = {
            "schema_version": SCHEMA_VERSION,
            "reservations": [record.to_json() for record in records],
        }
        atomic_write_text_content(
            self.ledger_path,
            serialize_json_pretty_sorted_strict(
                filter_json_mapping_strict(
                    payload,
                    error_message="Disk reservation ledger must be JSON-compatible.",
                ),
            ),
            file_mode=0o600,
            fsync_parent_directory=True,
        )

    def _read_payload_locked(self) -> JSONDict:
        try:
            with open_text(self.ledger_path, mode="r", encoding="utf-8", errors="strict") as handle:
                return parse_json_dict(handle.read(), field="disk reservation ledger")
        except OSError as exception:
            raise StateError(
                "Failed to read disk reservation ledger.",
                details={"path": self.ledger_path},
                cause=exception,
            ) from exception
        except ValidationError as exception:
            raise StateError(
                "Disk reservation ledger is invalid.",
                details={"path": self.ledger_path},
                cause=exception,
            ) from exception


def _parse_record_entry(value: JSONValue) -> DiskReservationRecord:
    if not isinstance(value, dict):
        raise StateError("Disk reservation ledger entry must be an object.")
    return parse_disk_reservation_record(value)
