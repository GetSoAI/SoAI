"""SoAI - Atomic wizard download predecessor validation [backend/database/repositories/tasks/wizard_download_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.database.mutation_requests import MutationAdmissionOutcome, MutationAdmissionRequest
from core.errors.exceptions import ValidationError

__all__ = ("sync_check_wizard_download_admission",)


def sync_check_wizard_download_admission(
    connection: sqlite3.Connection, request: MutationAdmissionRequest
) -> MutationAdmissionOutcome | None:
    previous = connection.execute(
        """SELECT request_id, accepted_task_id, lifecycle_status FROM mutation_admissions
        WHERE operation_type='wizard_model_download' AND owner_id=?
        ORDER BY accepted_at_ms DESC, rowid DESC LIMIT 1""",
        (request.owner_id,),
    ).fetchone()
    if previous is None:
        if request.supersedes_request_id is not None:
            raise ValidationError("The previous wizard download could not be verified.")
        return None
    if (
        previous["lifecycle_status"] not in ("failed", "cancelled")
        or request.supersedes_request_id != previous["request_id"]
    ):
        return MutationAdmissionOutcome(outcome="conflict", task_id=previous["accepted_task_id"])
    return None
