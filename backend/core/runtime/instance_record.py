"""SoAI - Strict V1 runtime instance record persistence [backend/core/runtime/instance_record.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from uuid import UUID, uuid4

import psutil

from core.errors.exceptions import StateError, ValidationError
from core.filesystem.atomic_writes import atomic_write_text_content
from core.filesystem.open_files import read_regular_file_no_symlink
from core.licensing.edition import require_licensing_edition
from core.runtime.api_endpoint import RuntimeApiEndpoint
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_value
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from core.types.json_value import require_json_dict

__all__ = (
    "RUNTIME_RECORD_SCHEMA_VERSION",
    "RuntimeInstanceRecord",
    "canonicalize_runtime_base_dir",
    "create_runtime_instance_record",
    "read_runtime_instance_record",
    "read_verified_runtime_instance_record",
    "runtime_record_matches_current_process",
    "runtime_record_process_descends_from",
    "runtime_record_matches_process_tree",
    "write_runtime_instance_record",
)

RUNTIME_RECORD_SCHEMA_VERSION = 1


def canonicalize_runtime_base_dir(base_dir: str) -> str:
    if not isinstance(base_dir, str) or not base_dir.strip():
        raise ValidationError("Runtime instance base directory is required.")
    return os.path.normcase(os.path.realpath(os.path.abspath(base_dir)))


@dataclass(frozen=True, slots=True)
class RuntimeInstanceRecord:
    runtime_id: str
    edition: str
    pid: int
    process_create_time_ns: int
    base_dir: str
    started_at_epoch_ms: int
    api_endpoint: RuntimeApiEndpoint | None

    def __post_init__(self) -> None:
        try:
            normalized_runtime_id = str(UUID(self.runtime_id))
        except ValueError as exception:
            raise ValidationError("Runtime instance ID must be a UUID.") from exception
        if normalized_runtime_id != self.runtime_id:
            raise ValidationError("Runtime instance ID must use canonical UUID formatting.")
        require_licensing_edition(self.edition)
        if not isinstance(self.pid, int) or isinstance(self.pid, bool) or self.pid <= 0:
            raise ValidationError("Runtime instance PID must be a positive integer.")
        if (
            not isinstance(self.process_create_time_ns, int)
            or isinstance(self.process_create_time_ns, bool)
            or self.process_create_time_ns <= 0
        ):
            raise ValidationError("Runtime process creation time must be a positive integer.")
        if self.base_dir != canonicalize_runtime_base_dir(self.base_dir):
            raise ValidationError("Runtime instance base directory must be canonical.")
        if (
            not isinstance(self.started_at_epoch_ms, int)
            or isinstance(self.started_at_epoch_ms, bool)
            or self.started_at_epoch_ms <= 0
        ):
            raise ValidationError("Runtime instance start time must be a positive integer.")

    def with_api_endpoint(self, endpoint: RuntimeApiEndpoint) -> RuntimeInstanceRecord:
        return replace(self, api_endpoint=endpoint)

    def to_mapping(self) -> JSONDict:
        return {
            "schema_version": RUNTIME_RECORD_SCHEMA_VERSION,
            "runtime_id": self.runtime_id,
            "edition": self.edition,
            "pid": self.pid,
            "process_create_time_ns": self.process_create_time_ns,
            "base_dir": self.base_dir,
            "started_at_epoch_ms": self.started_at_epoch_ms,
            "api_endpoint": (
                self.api_endpoint.to_record_payload() if self.api_endpoint is not None else None
            ),
        }

    @classmethod
    def from_mapping(cls, payload: JSONDict) -> RuntimeInstanceRecord:
        if set(payload) != {
            "schema_version",
            "runtime_id",
            "edition",
            "pid",
            "process_create_time_ns",
            "base_dir",
            "started_at_epoch_ms",
            "api_endpoint",
        }:
            raise ValidationError("Runtime instance record fields are invalid.")
        schema_version = payload["schema_version"]
        if schema_version != RUNTIME_RECORD_SCHEMA_VERSION or isinstance(schema_version, bool):
            raise ValidationError("Runtime instance record schema version is invalid.")
        runtime_id = payload["runtime_id"]
        edition = payload["edition"]
        pid = payload["pid"]
        process_create_time_ns = payload["process_create_time_ns"]
        base_dir = payload["base_dir"]
        started_at_epoch_ms = payload["started_at_epoch_ms"]
        endpoint_value = payload["api_endpoint"]
        if (
            not isinstance(runtime_id, str)
            or not isinstance(edition, str)
            or not isinstance(base_dir, str)
        ):
            raise ValidationError("Runtime instance record string fields are invalid.")
        if not isinstance(pid, int) or isinstance(pid, bool):
            raise ValidationError("Runtime instance record PID must be an integer.")
        if not isinstance(process_create_time_ns, int) or isinstance(
            process_create_time_ns,
            bool,
        ):
            raise ValidationError("Runtime process creation time must be an integer.")
        if not isinstance(started_at_epoch_ms, int) or isinstance(started_at_epoch_ms, bool):
            raise ValidationError("Runtime instance start time must be an integer.")
        endpoint = None
        if endpoint_value is not None:
            endpoint = RuntimeApiEndpoint.from_record_payload(
                require_json_dict(endpoint_value, label="runtime API endpoint"),
            )
        return cls(
            runtime_id=runtime_id,
            edition=edition,
            pid=pid,
            process_create_time_ns=process_create_time_ns,
            base_dir=base_dir,
            started_at_epoch_ms=started_at_epoch_ms,
            api_endpoint=endpoint,
        )


def create_runtime_instance_record(
    *,
    pid: int,
    base_dir: str,
    edition: str,
) -> RuntimeInstanceRecord:
    try:
        process_create_time_ns = int(round(psutil.Process(pid).create_time() * 1_000_000_000))
    except psutil.Error as exception:
        raise StateError("Could not resolve runtime process identity.") from exception
    return RuntimeInstanceRecord(
        runtime_id=str(uuid4()),
        edition=require_licensing_edition(edition),
        pid=pid,
        process_create_time_ns=process_create_time_ns,
        base_dir=canonicalize_runtime_base_dir(base_dir),
        started_at_epoch_ms=int(epoch_ms()),
        api_endpoint=None,
    )


def read_runtime_instance_record(record_path: str) -> RuntimeInstanceRecord:
    try:
        raw_payload = read_regular_file_no_symlink(record_path)
    except ValidationError as exception:
        if isinstance(exception.__cause__, FileNotFoundError):
            missing_record = exception.__cause__
            raise FileNotFoundError(
                missing_record.errno, missing_record.strerror, missing_record.filename
            ) from exception
        raise
    parsed_payload = parse_json_value(
        raw_payload, field="runtime instance record", strict_utf8=True, reject_duplicate_keys=True
    )
    return RuntimeInstanceRecord.from_mapping(
        require_json_dict(parsed_payload, label="runtime instance record"),
    )


def read_verified_runtime_instance_record(
    record_path: str,
    *,
    base_dir: str,
    expected_edition: str | None = None,
    expected_pid: int | None = None,
) -> RuntimeInstanceRecord | None:
    try:
        record = read_runtime_instance_record(record_path)
    except FileNotFoundError:
        return None
    if record.base_dir != canonicalize_runtime_base_dir(base_dir):
        raise ValidationError("Runtime instance record belongs to another installation.")
    if expected_edition is not None and record.edition != require_licensing_edition(
        expected_edition
    ):
        raise ValidationError("Runtime instance record belongs to another edition.")
    if expected_pid is not None and record.pid != expected_pid:
        raise ValidationError("Runtime instance record PID does not match the expected process.")
    try:
        process = psutil.Process(record.pid)
        process_create_time_ns = int(round(process.create_time() * 1_000_000_000))
        if not process.is_running():
            return None
    except psutil.NoSuchProcess:
        return None
    except psutil.Error as exception:
        raise StateError("Runtime process identity could not be verified.") from exception
    if process_create_time_ns != record.process_create_time_ns:
        return None
    return record


def write_runtime_instance_record(
    record_path: str,
    record: RuntimeInstanceRecord,
) -> None:
    atomic_write_text_content(
        record_path,
        serialize_json_compact_stable_strict(record.to_mapping()),
        encoding="utf-8",
        errors="strict",
        fsync=True,
        file_mode=0o600,
        fsync_parent_directory=True,
    )


def runtime_record_matches_current_process(
    record: RuntimeInstanceRecord,
    *,
    base_dir: str,
    expected_edition: str,
) -> bool:
    current_pid = os.getpid()
    if record.pid != current_pid:
        return False
    if record.base_dir != canonicalize_runtime_base_dir(base_dir):
        return False
    if record.edition != require_licensing_edition(expected_edition):
        return False
    try:
        process_create_time_ns = int(
            round(psutil.Process(current_pid).create_time() * 1_000_000_000),
        )
    except psutil.Error:
        return False
    return record.process_create_time_ns == process_create_time_ns


def runtime_record_process_descends_from(
    record: RuntimeInstanceRecord,
    ancestor_pid: int,
    *,
    ancestor_create_time_ns: int | None = None,
) -> bool:
    try:
        process = psutil.Process(record.pid)
        if ancestor_create_time_ns is not None and (
            int(round(process.create_time() * 1_000_000_000)) != record.process_create_time_ns
        ):
            return False
        for parent in process.parents():
            if parent.pid == ancestor_pid:
                return ancestor_create_time_ns is None or (
                    int(round(parent.create_time() * 1_000_000_000)) == ancestor_create_time_ns
                )
    except psutil.Error:
        return False
    return False


def runtime_record_matches_process_tree(
    record: RuntimeInstanceRecord, expected: RuntimeInstanceRecord
) -> bool:
    if record.edition != expected.edition or record.base_dir != expected.base_dir:
        return False
    if record.pid == expected.pid:
        return record.process_create_time_ns == expected.process_create_time_ns
    return runtime_record_process_descends_from(
        record, expected.pid, ancestor_create_time_ns=expected.process_create_time_ns
    )
