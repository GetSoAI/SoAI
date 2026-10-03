"""SoAI - Automation definition revision tokens and edit preconditions [backend/core/automation/automation_revision.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from core.automation.automation_constants import AUTOMATION_PAYLOAD_FIELDS
from core.errors.exceptions import AutomationRevisionConflictError, StateError
from core.serialization.json import serialize_json_compact_stable_strict

if TYPE_CHECKING:
    from collections.abc import Mapping

    from core.types.json import JSONDict, JSONValue

__all__ = (
    "compute_automation_revision",
    "require_automation_revision_match",
)


def compute_automation_revision(record: Mapping[str, JSONValue]) -> str:
    editable: JSONDict = {}
    for field_name in AUTOMATION_PAYLOAD_FIELDS:
        if field_name not in record:
            raise StateError(f"Automation is missing editable field '{field_name}'.")
        editable[field_name] = record[field_name]
    canonical = serialize_json_compact_stable_strict(editable)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def require_automation_revision_match(
    current: Mapping[str, JSONValue],
    expected_revision: str | None,
) -> None:
    if expected_revision is None:
        return
    current_revision = compute_automation_revision(current)
    if current_revision != expected_revision:
        raise AutomationRevisionConflictError(
            "Automation changed since it was loaded. Reload it and review the latest definition.",
            details={"current_revision": current_revision},
        )
