"""SoAI - Shared batch upload metadata parsing [backend/core/files/upload_batch_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import PayloadTooLargeError, ValidationError
from core.files.upload_relative_paths import normalize_batch_upload_relative_path
from core.files.upload_size_validation import (
    UPLOAD_MAX_SIZE_EXCEEDED_MESSAGE,
    ensure_safe_frontend_integer,
)
from core.files.upload_validation import normalize_non_negative_size
from core.serialization.json_parsing import parse_json_value
from core.validation.integers import coerce_exact_int_or_none

__all__ = (
    "parse_relative_paths_json",
    "parse_relative_sizes_json",
)


def parse_relative_paths_json(value: str, *, field_name: str = "relative_paths") -> list[str]:
    try:
        parsed = parse_json_value(value)
    except ValidationError as exception:
        raise ValidationError(f"{field_name} must be valid JSON array.") from exception
    if not isinstance(parsed, list) or not parsed:
        raise ValidationError(f"{field_name} must be a non-empty JSON array.")
    resolved: list[str] = []
    for index, item in enumerate(parsed):
        if not isinstance(item, str):
            raise ValidationError(f"{field_name}[{index}] must be a string.")
        normalized = item.strip()
        if not normalized:
            raise ValidationError(f"{field_name}[{index}] must be a non-empty string.")
        resolved.append(normalize_batch_upload_relative_path(normalized))
    return resolved


def parse_relative_sizes_json(
    value: str,
    *,
    max_file_bytes: int | None,
    field_name: str = "relative_sizes",
    allow_null_items: bool,
    allow_number_items: bool,
) -> tuple[list[int | None], int]:
    try:
        parsed = parse_json_value(value)
    except ValidationError as exception:
        raise ValidationError(f"{field_name} must be valid JSON array.") from exception
    if not isinstance(parsed, list) or not parsed:
        raise ValidationError(f"{field_name} must be a non-empty JSON array.")
    resolved: list[int | None] = []
    total = 0
    for index, item in enumerate(parsed):
        if item is None:
            if not allow_null_items:
                raise ValidationError(f"{field_name}[{index}] must be an integer.")
            resolved.append(None)
            continue
        if isinstance(item, bool):
            raise ValidationError(_size_error_message(field_name, index, allow_number_items))
        if allow_number_items:
            if not isinstance(item, int | float):
                raise ValidationError(_size_error_message(field_name, index, allow_number_items))
            exact_item = coerce_exact_int_or_none(item)
            if exact_item is None:
                raise ValidationError(_size_error_message(field_name, index, allow_number_items))
            normalized = normalize_non_negative_size(
                exact_item,
                field_name=f"{field_name}[{index}]",
            )
        else:
            if not isinstance(item, int):
                raise ValidationError(_size_error_message(field_name, index, allow_number_items))
            normalized = normalize_non_negative_size(
                item,
                field_name=f"{field_name}[{index}]",
            )
        if normalized is None:
            raise ValidationError(_size_error_message(field_name, index, allow_number_items))
        ensure_safe_frontend_integer(normalized, field_name=f"{field_name}[{index}]")
        if max_file_bytes is not None and normalized > max_file_bytes:
            raise PayloadTooLargeError(UPLOAD_MAX_SIZE_EXCEEDED_MESSAGE)
        resolved.append(int(normalized))
        total += int(normalized)
        ensure_safe_frontend_integer(total, field_name=f"{field_name} total")
    return resolved, total


def _size_error_message(field_name: str, index: int, allow_number_items: bool) -> str:
    if allow_number_items:
        return f"{field_name}[{index}] must be a number or null."
    return f"{field_name}[{index}] must be an integer."
