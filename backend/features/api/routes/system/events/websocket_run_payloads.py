"""SoAI - WebSocket run payload parsing helpers [backend/features/api/routes/system/events/websocket_run_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict
from core.validation.integers import require_non_negative_exact_int
from core.validation.strings import coerce_optional_trimmed_str

__all__ = (
    "require_non_negative_sequence",
    "require_run_id",
    "resolve_run_id",
)


def resolve_run_id(data: JSONDict) -> str | None:
    return coerce_optional_trimmed_str(data.get("run_id"))


def require_run_id(data: JSONDict) -> str:
    run_id = resolve_run_id(data)
    if run_id is None:
        raise ValidationError("run_id is required.")
    return run_id


def require_non_negative_sequence(data: JSONDict, *, field_name: str = "sequence") -> int:
    raw = data.get(field_name)
    return require_non_negative_exact_int(
        raw,
        type_message=f"{field_name} must be an integer.",
        range_message=f"{field_name} must be >= 0.",
    )
