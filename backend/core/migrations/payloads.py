"""SoAI - Typed mapping payload migration primitives [backend/core/migrations/payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeGuard

from core.errors.exceptions import StateError, ValidationError
from core.serialization.key_signatures import calculate_nested_mapping_keys_hash
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.serialization.key_signatures import NestedKeySignatureValue

__all__ = (
    "PayloadMigrationStep",
    "upgrade_mapping_payload_to_current",
)


@dataclass(frozen=True, slots=True)
class PayloadMigrationStep[ValueT]:
    migration_id: str
    signature_keys_hash: str
    apply: Callable[[dict[str, ValueT], LoggerProtocol], dict[str, ValueT]]


def _require_mapping_non_empty_string_keys[ValueT](
    value: Mapping[str, ValueT],
    *,
    label: str,
) -> None:
    for key in value:
        if not isinstance(key, str) or not key:
            raise StateError(f"{label} contains a non-string or empty key: {key!r}.")


def _index_steps[ValueT](
    steps: tuple[PayloadMigrationStep[ValueT], ...],
    *,
    migration_label: str,
) -> dict[str, PayloadMigrationStep[ValueT]]:
    ids: set[str] = set()
    indexed: dict[str, PayloadMigrationStep[ValueT]] = {}
    for step in steps:
        if step.migration_id != step.migration_id.strip():
            raise StateError(
                f"{migration_label} migration id must not contain leading/trailing whitespace.",
            )
        migration_id = step.migration_id
        if not migration_id.strip():
            raise StateError(f"{migration_label} migration id must be a non-empty string.")
        if migration_id in ids:
            raise StateError(f"Duplicate {migration_label} migration id: {migration_id!r}.")
        ids.add(migration_id)
        signature_hash = require_canonical_sha256_hexdigest(
            step.signature_keys_hash,
            label=f"{migration_label} migration {migration_id!r} signature hash",
        )
        if signature_hash in indexed:
            raise StateError(
                f"Duplicate {migration_label} migration signature hash for {indexed[signature_hash].migration_id!r} and {migration_id!r}.",
            )
        indexed[signature_hash] = step
    return indexed


def _build_payload_key_signature_value[ValueT](
    value: Mapping[str, ValueT],
) -> NestedKeySignatureValue:
    mapped: dict[str, NestedKeySignatureValue] = {}
    for raw_key, nested in value.items():
        if not isinstance(raw_key, str) or not raw_key:
            raise ValidationError("Mapping contains a non-string or empty key.")
        if _is_mapping_value(nested):
            mapped[raw_key] = _build_payload_key_signature_value(nested)
            continue
        if _is_collection_value(nested):
            mapped[raw_key] = _build_payload_key_signature_items(nested)
            continue
        mapped[raw_key] = None
    return mapped


def _build_payload_key_signature_items[ValueT](
    value: list[ValueT] | tuple[ValueT, ...] | set[ValueT] | frozenset[ValueT],
) -> NestedKeySignatureValue:
    nested_items: list[NestedKeySignatureValue] = []
    for nested in value:
        if _is_mapping_value(nested):
            nested_items.append(_build_payload_key_signature_value(nested))
            continue
        if _is_collection_value(nested):
            nested_items.append(_build_payload_key_signature_items(nested))
            continue
    return nested_items


def _is_mapping_value[ValueT](value: ValueT) -> TypeGuard[Mapping[str, ValueT]]:
    return isinstance(value, Mapping)


def _is_collection_value[ValueT](
    value: ValueT,
) -> TypeGuard[list[ValueT] | tuple[ValueT, ...] | set[ValueT] | frozenset[ValueT]]:
    return isinstance(value, list | tuple | set | frozenset)


def upgrade_mapping_payload_to_current[ValueT](
    payload: dict[str, ValueT],
    *,
    steps: tuple[PayloadMigrationStep[ValueT], ...],
    logger: LoggerProtocol,
    max_steps: int,
    payload_label: str,
    migration_label: str,
    non_mapping_input_message: str,
    non_mapping_output_message: str,
) -> tuple[dict[str, ValueT], tuple[str, ...]]:
    if not isinstance(payload, Mapping):
        raise ValidationError(non_mapping_input_message)
    for key in payload:
        if not isinstance(key, str) or not key:
            raise ValidationError(f"{payload_label} contains a non-string or empty key.")

    steps_by_signature = _index_steps(steps, migration_label=migration_label)
    working = dict(payload)
    applied_ids: list[str] = []

    for _ in range(max_steps):
        working_hash = calculate_nested_mapping_keys_hash(
            _build_payload_key_signature_value(working),
        )
        step = steps_by_signature.get(working_hash)
        if step is None:
            return (working, tuple(applied_ids))
        if step.migration_id in applied_ids:
            raise StateError(
                f"{migration_label} migration cycle detected at: {step.migration_id!r}.",
            )
        logger.warning("%s migration: applying %s", migration_label, step.migration_id)
        upgraded = step.apply(working, logger)
        if not isinstance(upgraded, Mapping):
            raise StateError(
                f"{migration_label} migration {step.migration_id!r} {non_mapping_output_message}",
            )
        _require_mapping_non_empty_string_keys(
            upgraded,
            label=f"{migration_label} migration {step.migration_id!r} output",
        )
        working = dict(upgraded)
        applied_ids.append(step.migration_id)

    working_hash = calculate_nested_mapping_keys_hash(_build_payload_key_signature_value(working))
    step = steps_by_signature.get(working_hash)
    if step is None:
        return (working, tuple(applied_ids))
    if step.migration_id in applied_ids:
        raise StateError(f"{migration_label} migration cycle detected at: {step.migration_id!r}.")
    raise StateError(f"{migration_label} migration exceeded max steps.")
