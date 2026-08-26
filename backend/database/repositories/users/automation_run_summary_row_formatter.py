"""SoAI - Automation run summary row formatter [backend/database/repositories/users/automation_run_summary_row_formatter.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.types.json import JSONDict
from database.core.sqlite_values import SQLiteRowDict
from database.repositories.users.automation_row_parsing import (
    parse_automation_run_shared_fields,
)

__all__ = ("format_automation_run_summary_row",)

_LABEL_PREFIX = "Automation run summary field"


def format_automation_run_summary_row(
    row: SQLiteRowDict | None,
) -> JSONDict | None:
    if not row:
        return None
    return parse_automation_run_shared_fields(
        row,
        build_error=StateError,
        label_prefix=_LABEL_PREFIX,
    )
