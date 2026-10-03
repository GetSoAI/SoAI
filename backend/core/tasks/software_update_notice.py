"""SoAI - Durable per-user software update outcome notice [backend/core/tasks/software_update_notice.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.filesystem.atomic_writes import atomic_write_json_content
from core.filesystem.open_files import open_binary
from core.meta.paths import join_data_abs
from core.serialization.json_parsing import parse_json_dict
from core.tasks.identifiers import validate_optional_task_id
from core.tasks.software_update_versions import require_software_update_version

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "SOFTWARE_UPDATE_NOTICE_STATUSES",
    "SoftwareUpdateNotice",
    "acknowledge_software_update_notice",
    "publish_software_update_notice",
    "read_software_update_notice",
    "software_update_notice_path",
)

SCHEMA_VERSION = 1
NOTICE_FILENAME = "software-update-notice-v1.json"
MAX_NOTICE_BYTES = 262144
MAX_ACKNOWLEDGED_USERS = 10000
SOFTWARE_UPDATE_NOTICE_STATUSES = frozenset({"completed", "failed"})
NOTICE_FIELDS = frozenset(
    {
        "schema_version",
        "task_id",
        "status",
        "from_version",
        "to_version",
        "finished_at_ms",
        "acknowledged_user_ids",
    }
)


@dataclass(frozen=True, slots=True)
class SoftwareUpdateNotice:
    task_id: str
    status: str
    from_version: str
    to_version: str
    finished_at_ms: int
    acknowledged_user_ids: tuple[int, ...]

    def is_acknowledged_by(self, user_id: int) -> bool:
        return user_id in self.acknowledged_user_ids

    def to_public_payload(self) -> JSONDict:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "finished_at_ms": self.finished_at_ms,
        }


def software_update_notice_path(base_path: str) -> str:
    return join_data_abs(base_path, "state", NOTICE_FILENAME)


def _require_non_negative_int(value: JSONValue, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer.")
    return value


def _validated_notice(
    *,
    task_id: JSONValue,
    status: JSONValue,
    from_version: JSONValue,
    to_version: JSONValue,
    finished_at_ms: JSONValue,
    acknowledged_user_ids: tuple[JSONValue, ...],
) -> SoftwareUpdateNotice:
    normalized_task_id = validate_optional_task_id(
        task_id,
        field_name="software update notice task_id",
    )
    if normalized_task_id is None:
        raise ValidationError("software update notice task_id is required.")
    if not isinstance(status, str) or status not in SOFTWARE_UPDATE_NOTICE_STATUSES:
        raise ValidationError("Software update notice status is invalid.")
    if len(acknowledged_user_ids) > MAX_ACKNOWLEDGED_USERS:
        raise ValidationError("Software update notice has too many acknowledgements.")
    user_ids = tuple(
        _require_non_negative_int(value, field="software update notice acknowledged user id")
        for value in acknowledged_user_ids
    )
    if len(frozenset(user_ids)) != len(user_ids):
        raise ValidationError("Software update notice acknowledgements must be unique.")
    return SoftwareUpdateNotice(
        task_id=normalized_task_id,
        status=status,
        from_version=require_software_update_version(
            from_version,
            field="software update notice from_version",
        ),
        to_version=require_software_update_version(
            to_version,
            field="software update notice to_version",
        ),
        finished_at_ms=_require_non_negative_int(
            finished_at_ms,
            field="software update notice finished_at_ms",
        ),
        acknowledged_user_ids=user_ids,
    )


def _write_notice(base_path: str, notice: SoftwareUpdateNotice) -> None:
    atomic_write_json_content(
        software_update_notice_path(base_path),
        {
            "schema_version": SCHEMA_VERSION,
            "task_id": notice.task_id,
            "status": notice.status,
            "from_version": notice.from_version,
            "to_version": notice.to_version,
            "finished_at_ms": notice.finished_at_ms,
            "acknowledged_user_ids": list(notice.acknowledged_user_ids),
        },
        fsync_parent_directory=True,
    )


def publish_software_update_notice(
    base_path: str,
    *,
    task_id: str,
    status: str,
    from_version: str,
    to_version: str,
    finished_at_ms: int,
) -> None:
    _write_notice(
        base_path,
        _validated_notice(
            task_id=task_id,
            status=status,
            from_version=from_version,
            to_version=to_version,
            finished_at_ms=finished_at_ms,
            acknowledged_user_ids=(),
        ),
    )


def read_software_update_notice(base_path: str) -> SoftwareUpdateNotice | None:
    notice_path = software_update_notice_path(base_path)
    try:
        file_size = os.path.getsize(notice_path)
    except FileNotFoundError:
        return None
    if file_size <= 0 or file_size > MAX_NOTICE_BYTES:
        raise ValidationError("Software update notice size is invalid.")
    with open_binary(notice_path, mode="rb") as notice_file:
        payload = parse_json_dict(
            notice_file.read(MAX_NOTICE_BYTES + 1),
            field="software update notice",
            reject_duplicate_keys=True,
        )
    if frozenset(payload) != NOTICE_FIELDS:
        raise ValidationError("Software update notice fields do not match the V1 contract.")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValidationError("Software update notice schema_version must be 1.")
    acknowledged = payload.get("acknowledged_user_ids")
    if not isinstance(acknowledged, list):
        raise ValidationError("Software update notice acknowledgements must be a list.")
    return _validated_notice(
        task_id=payload.get("task_id"),
        status=payload.get("status"),
        from_version=payload.get("from_version"),
        to_version=payload.get("to_version"),
        finished_at_ms=payload.get("finished_at_ms"),
        acknowledged_user_ids=tuple(acknowledged),
    )


def acknowledge_software_update_notice(base_path: str, *, task_id: str, user_id: int) -> bool:
    notice = read_software_update_notice(base_path)
    if notice is None or notice.task_id != task_id:
        return False
    if notice.is_acknowledged_by(user_id):
        return True
    _write_notice(
        base_path,
        _validated_notice(
            task_id=notice.task_id,
            status=notice.status,
            from_version=notice.from_version,
            to_version=notice.to_version,
            finished_at_ms=notice.finished_at_ms,
            acknowledged_user_ids=(*notice.acknowledged_user_ids, user_id),
        ),
    )
    return True
