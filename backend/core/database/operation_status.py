"""SoAI - Database operation status contracts [backend/core/database/operation_status.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

__all__ = ("DatabaseOperationStatus", "DatabaseOperationStatusValue")


class DatabaseOperationStatusValue(StrEnum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMMITTED = "committed"
    FAILED = "failed"
    SKIPPED = "skipped"
    OUTCOME_UNKNOWN = "outcome_unknown"
    NOT_COMMITTED = "not_committed"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class DatabaseOperationStatus:
    operation_id: str
    status: DatabaseOperationStatusValue
    terminal: bool
    retry_safe: bool
    committed_at_ms: int | None
    expires_at_ms: int
