"""SoAI - Snapshot payload validation helpers [backend/features/api/routes/system/events/snapshots/payload_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("require_supported_snapshot_payload_keys",)


def require_supported_snapshot_payload_keys(
    data: JSONDict,
    *,
    allowed_keys: set[str],
) -> None:
    for key in data:
        if isinstance(key, str) and key not in allowed_keys:
            raise ValidationError("Snapshot payload contains unsupported fields.")
