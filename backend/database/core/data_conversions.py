"""SoAI - Database data conversions and constants [backend/database/core/data_conversions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable_strict

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "normalize_kv_map",
    "resolve_delete_statement",
    "resolve_prune_statement",
    "serialize_optional_map",
    "validate_retention_hours",
)

SQLITE_BATCH_SIZE = 900

ALLOWED_PRUNE_TABLES = frozenset(
    (
        "hardware_cpu_history",
        "hardware_gpu_history",
        "hardware_disk_history",
        "hardware_network_history",
        "metrics_history",
    ),
)

PRUNE_STATEMENT_PAIRS: tuple[tuple[str, str], ...] = (
    ("hardware_cpu_history", "DELETE FROM hardware_cpu_history WHERE observed_at_ms < ?"),
    ("hardware_gpu_history", "DELETE FROM hardware_gpu_history WHERE observed_at_ms < ?"),
    ("hardware_disk_history", "DELETE FROM hardware_disk_history WHERE observed_at_ms < ?"),
    ("hardware_network_history", "DELETE FROM hardware_network_history WHERE observed_at_ms < ?"),
    ("metrics_history", "DELETE FROM metrics_history WHERE observed_at_ms < ?"),
)

ALLOWED_DELETE_TARGETS = frozenset(
    {
        ("models_catalog", "universal_id"),
        ("files_catalog", "id"),
    },
)

DELETE_STATEMENT_PAIRS: tuple[tuple[tuple[str, str], str], ...] = (
    (("models_catalog", "universal_id"), "DELETE FROM models_catalog WHERE universal_id = ?"),
    (("files_catalog", "id"), "DELETE FROM files_catalog WHERE id = ?"),
)


def resolve_prune_statement(table: str) -> str:
    if table not in ALLOWED_PRUNE_TABLES:
        raise ValidationError(f"Table '{table}' not in prune allowlist")
    for allowed_table, statement in PRUNE_STATEMENT_PAIRS:
        if table == allowed_table:
            return statement
    raise ValidationError(f"Missing prune statement for table '{table}'")


def resolve_delete_statement(table: str, id_column: str) -> str:
    target = (table, id_column)
    if target not in ALLOWED_DELETE_TARGETS:
        raise ValidationError(f"Delete target '{table}.{id_column}' not in allowlist")
    for allowed_target, statement in DELETE_STATEMENT_PAIRS:
        if target == allowed_target:
            return statement
    raise ValidationError(f"Missing delete statement for target '{table}.{id_column}'")


def validate_retention_hours(retention_hours: float | str) -> int:
    if isinstance(retention_hours, bool):
        raise ValidationError(f"retention_hours must be an integer, got: {retention_hours}")
    try:
        sanitized_retention = int(retention_hours)
    except (TypeError, ValueError) as exception:
        raise ValidationError(
            f"retention_hours must be an integer, got: {retention_hours}",
        ) from exception
    if sanitized_retention < 0:
        raise ValidationError(f"retention_hours must be non-negative, got: {retention_hours}")
    return sanitized_retention


def normalize_kv_map(payload: JSONValue) -> dict[str, str]:
    if not isinstance(payload, dict):
        return {}
    normalized: dict[str, str] = {}
    for raw_key, raw_value in payload.items():
        key = str(raw_key or "").strip()
        if not key:
            continue
        normalized[key] = "" if raw_value is None else str(raw_value)
    return normalized


def serialize_optional_map(payload: dict[str, str] | None) -> str | None:
    if not payload:
        return None
    return serialize_json_compact_stable_strict(payload)
