"""SoAI - Durable software update result reconciliation [backend/core/tasks/software_update_result.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.bootstrap.install_filesystem import unlink_if_exists
from core.errors.exceptions import StateError, ValidationError
from core.filesystem.atomic_writes import atomic_write_json_content
from core.filesystem.open_files import open_binary
from core.meta.paths import join_data_abs
from core.runtime.soai_identifiers import (
    build_soai_id,
    create_prefixed_hex_id,
    safe_or_hashed_segment,
)
from core.serialization.json_parsing import parse_json_dict
from core.tasks.creation import create
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.identifiers import validate_optional_task_id
from core.tasks.type_catalog import TASK_TYPE_SOFTWARE_UPDATE
from core.validation.strings import coerce_required_non_empty_str

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "SoftwareUpdateResultRecord",
    "clear_software_update_result",
    "create_software_update_task",
    "create_software_update_task_id",
    "reconcile_software_update_result",
    "prepare_software_update_activation_task",
    "software_update_result_path",
    "write_software_update_result",
)

SCHEMA_VERSION = 1
RESULT_FILENAME = "software-update-result-v1.json"
MAX_RESULT_BYTES = 8192
VERSION_PATTERN = r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?\Z"


@dataclass(frozen=True, slots=True)
class SoftwareUpdateResultRecord:
    task_id: str
    from_version: str
    to_version: str
    status: str
    message: str


def create_software_update_task_id() -> str:
    return create_prefixed_hex_id("task")


def software_update_result_path(base_path: str) -> str:
    return join_data_abs(base_path, "state", RESULT_FILENAME)


def _require_version(value: JSONValue, *, field: str) -> str:
    version = coerce_required_non_empty_str(value, label=field)
    if re.fullmatch(VERSION_PATTERN, version) is None:
        raise ValidationError(f"{field} is invalid.")
    return version


def _validated_record(
    *,
    task_id: JSONValue,
    from_version: JSONValue,
    to_version: JSONValue,
    status: JSONValue,
    message: JSONValue,
) -> SoftwareUpdateResultRecord:
    normalized_task_id = validate_optional_task_id(
        task_id,
        field_name="software update result task_id",
    )
    if normalized_task_id is None:
        raise ValidationError("software update result task_id is required.")
    normalized_status = coerce_required_non_empty_str(
        status,
        label="software update result status",
    )
    if normalized_status not in {"installing", "completed", "failed", "cancelled"}:
        raise ValidationError("Software update result status is invalid.")
    normalized_message = coerce_required_non_empty_str(
        message,
        label="software update result message",
    )
    if len(normalized_message) > 1000:
        raise ValidationError("Software update result message is too long.")
    return SoftwareUpdateResultRecord(
        task_id=normalized_task_id,
        from_version=_require_version(
            from_version,
            field="software update result from_version",
        ),
        to_version=_require_version(
            to_version,
            field="software update result to_version",
        ),
        status=normalized_status,
        message=normalized_message,
    )


def _parse_record(raw: bytes) -> SoftwareUpdateResultRecord:
    payload = parse_json_dict(
        raw,
        field="software update result",
        reject_duplicate_keys=True,
    )
    if frozenset(payload) != frozenset(
        {"schema_version", "task_id", "from_version", "to_version", "status", "message"}
    ):
        raise ValidationError("Software update result fields do not match the V1 contract.")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValidationError("Software update result schema_version must be 1.")
    return _validated_record(
        task_id=payload.get("task_id"),
        from_version=payload.get("from_version"),
        to_version=payload.get("to_version"),
        status=payload.get("status"),
        message=payload.get("message"),
    )


def read_software_update_result(base_path: str) -> SoftwareUpdateResultRecord | None:
    result_path = software_update_result_path(base_path)
    try:
        file_size = os.path.getsize(result_path)
    except FileNotFoundError:
        return None
    if file_size <= 0 or file_size > MAX_RESULT_BYTES:
        raise ValidationError("Software update result size is invalid.")
    with open_binary(result_path, mode="rb") as result_file:
        return _parse_record(result_file.read(MAX_RESULT_BYTES + 1))


def write_software_update_result(
    base_path: str,
    *,
    task_id: str,
    from_version: str,
    to_version: str,
    status: str,
    message: str,
) -> None:
    record = _validated_record(
        task_id=task_id,
        from_version=from_version,
        to_version=to_version,
        status=status,
        message=message,
    )
    atomic_write_json_content(
        software_update_result_path(base_path),
        {
            "schema_version": SCHEMA_VERSION,
            "task_id": record.task_id,
            "from_version": record.from_version,
            "to_version": record.to_version,
            "status": record.status,
            "message": record.message,
        },
        fsync_parent_directory=True,
    )


def clear_software_update_result(base_path: str) -> None:
    unlink_if_exists(software_update_result_path(base_path))


async def create_software_update_task(
    registry: TaskRegistryProtocol,
    *,
    task_id: str,
    metadata: JSONDict,
) -> None:
    await create(
        registry,
        task_id=task_id,
        task_type=TASK_TYPE_SOFTWARE_UPDATE,
        owner_id="updater",
        owner_type="system",
        user_id=0,
        cancellation_id=build_soai_id(
            ("sys", "software_update", safe_or_hashed_segment(task_id)),
        ),
        metadata=metadata,
    )


async def prepare_software_update_activation_task(
    registry: TaskRegistryProtocol,
    *,
    base_path: str,
    task_id: str,
    from_version: str,
    to_version: str,
) -> None:
    record = read_software_update_result(base_path)
    if (
        record is None
        or record.task_id != task_id
        or record.from_version != from_version
        or record.to_version != to_version
        or record.status != "installing"
    ):
        raise StateError("Pending activation does not match its durable update result.")
    task = await registry.get(task_id)
    if task is None:
        await create_software_update_task(
            registry,
            task_id=task_id,
            metadata={"from_version": from_version, "to_version": to_version},
        )
        task = await registry.get(task_id)
    if (
        task is None
        or task.task_type != TASK_TYPE_SOFTWARE_UPDATE
        or task.owner_type != "system"
        or task.owner_id != "updater"
        or task.status.is_terminal()
    ):
        raise StateError("Pending activation requires an active task owned by the updater.")


async def reconcile_software_update_result(
    registry: TaskRegistryProtocol,
    *,
    base_path: str,
) -> bool:
    record = read_software_update_result(base_path)
    if record is None:
        return False
    task_id = record.task_id
    task = await registry.get(task_id)
    if task is None:
        await create_software_update_task(
            registry,
            task_id=task_id,
            metadata={
                "from_version": record.from_version,
                "to_version": record.to_version,
                "auto_created": True,
            },
        )
    if record.status == "completed":
        expected_status = TaskStatus.COMPLETED
        terminal_task = await finalize(
            registry,
            task_id,
            TaskStatus.COMPLETED,
            result={
                "from_version": record.from_version,
                "to_version": record.to_version,
                "message": record.message,
            },
        )
    elif record.status == "cancelled":
        expected_status = TaskStatus.CANCELLED
        terminal_task = await finalize(
            registry,
            task_id,
            TaskStatus.CANCELLED,
            status_message=record.message,
        )
    else:
        expected_status = TaskStatus.FAILED
        failure_message = (
            "Software update was interrupted before completion."
            if record.status == "installing"
            else record.message
        )
        terminal_task = await finalize(
            registry,
            task_id,
            TaskStatus.FAILED,
            error_code=500,
            error_message=failure_message,
            status_message=failure_message,
        )
    if terminal_task is None or terminal_task.status != expected_status:
        raise StateError("Software update task terminal state conflicts with its durable result.")
    clear_software_update_result(base_path)
    return True
