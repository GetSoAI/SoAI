"""SoAI - Shared PTY validation and geometry policy [backend/core/terminal/pty_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = (
    "DEFAULT_PTY_COLS",
    "DEFAULT_PTY_ROWS",
    "clamp_pty_dimensions",
    "normalize_required_session_id",
    "require_positive_pty_dimensions",
    "resolve_default_pty_dimensions",
)

DEFAULT_PTY_COLS = 80
DEFAULT_PTY_ROWS = 24
_MAX_PTY_COLS = 500
_MAX_PTY_ROWS = 200


def _require_integer_dimensions(cols: int, rows: int) -> tuple[int, int]:
    if (
        (not isinstance(cols, int))
        or isinstance(cols, bool)
        or (not isinstance(rows, int))
        or isinstance(rows, bool)
    ):
        raise ValidationError("cols and rows must be integers.")
    return (cols, rows)


def _resolve_optional_dimension(value: int | None, fallback: int) -> int:
    if value is None:
        return fallback
    if (not isinstance(value, int)) or isinstance(value, bool):
        raise ValidationError("cols and rows must be integers.")
    if value == 0:
        return fallback
    return value


def normalize_required_session_id(
    session_id: str,
    *,
    error_message: str = "session_id is required.",
) -> str:
    if not isinstance(session_id, str):
        raise ValidationError(error_message)
    normalized = session_id.strip()
    if not normalized:
        raise ValidationError(error_message)
    return normalized


def require_positive_pty_dimensions(cols: int, rows: int) -> tuple[int, int]:
    cols, rows = _require_integer_dimensions(cols, rows)
    if cols <= 0 or rows <= 0:
        raise ValidationError("cols and rows must be positive.")
    return (cols, rows)


def clamp_pty_dimensions(cols: int, rows: int) -> tuple[int, int]:
    cols, rows = _require_integer_dimensions(cols, rows)
    return (
        max(1, min(cols, _MAX_PTY_COLS)),
        max(1, min(rows, _MAX_PTY_ROWS)),
    )


def resolve_default_pty_dimensions(cols: int | None, rows: int | None) -> tuple[int, int]:
    resolved_cols = _resolve_optional_dimension(cols, DEFAULT_PTY_COLS)
    resolved_rows = _resolve_optional_dimension(rows, DEFAULT_PTY_ROWS)
    return (resolved_cols, resolved_rows)
