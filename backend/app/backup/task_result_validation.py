"""SoAI - Backup task result validation [backend/app/backup/task_result_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from core.backup.types import BackupFileEntry
    from core.types.json import JSONDict, JSONValue

__all__ = ("require_backup_bool_field", "require_backup_bool_value")


def require_backup_bool_value(value: JSONValue, *, error_message: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(error_message)
    return value


def require_backup_bool_field(
    payload: BackupFileEntry | JSONDict | Mapping[str, JSONValue],
    *,
    field_name: str,
    error_message: str,
) -> bool:
    value = payload.get(field_name)
    if not isinstance(value, bool):
        raise ValidationError(error_message)
    return require_backup_bool_value(value, error_message=error_message)
