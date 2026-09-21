"""SoAI - Archive planning resource budgets [backend/core/archives/resource_limits.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.validation.requirements import require_non_negative_exact_int

__all__ = (
    "ArchivePlanningBudget",
    "ArchiveResourceLimits",
    "default_archive_resource_limits",
    "encoded_metadata_size",
)


@dataclass(frozen=True, slots=True)
class ArchiveResourceLimits:
    max_members: int
    max_materialized_entries: int
    max_expanded_bytes: int
    max_entry_metadata_bytes: int
    max_aggregate_metadata_bytes: int

    def __post_init__(self) -> None:
        values = (
            ("max_members", self.max_members),
            ("max_materialized_entries", self.max_materialized_entries),
            ("max_expanded_bytes", self.max_expanded_bytes),
            ("max_entry_metadata_bytes", self.max_entry_metadata_bytes),
            ("max_aggregate_metadata_bytes", self.max_aggregate_metadata_bytes),
        )
        for label, value in values:
            normalized = require_non_negative_exact_int(
                value,
                type_message=f"Archive resource limit {label} must be an integer.",
                range_message=f"Archive resource limit {label} must not be negative.",
            )
            if normalized == 0:
                raise ValidationError(f"Archive resource limit {label} must be positive.")


def default_archive_resource_limits() -> ArchiveResourceLimits:
    return ArchiveResourceLimits(
        max_members=250_000,
        max_materialized_entries=250_000,
        max_expanded_bytes=1 << 40,
        max_entry_metadata_bytes=8 * 1024,
        max_aggregate_metadata_bytes=128 * 1024 * 1024,
    )


class ArchivePlanningBudget:
    def __init__(self, limits: ArchiveResourceLimits) -> None:
        self._limits = limits
        self._members = 0
        self._materialized_entries = 0
        self._expanded_bytes = 0
        self._metadata_bytes = 0

    @property
    def expanded_bytes(self) -> int:
        return self._expanded_bytes

    def add_member(self, *, metadata_bytes: int, name: str) -> None:
        normalized_metadata = self._require_size(metadata_bytes, name)
        if normalized_metadata > self._limits.max_entry_metadata_bytes:
            raise ValidationError(
                f"Archive member metadata exceeds the limit of {self._limits.max_entry_metadata_bytes} bytes: {name}",
            )
        next_members = self._members + 1
        if next_members > self._limits.max_members:
            raise ValidationError(
                f"Archive exceeds the member limit of {self._limits.max_members}.",
            )
        self._members = next_members
        self._add_metadata(normalized_metadata, name)

    def add_materialized_entry(self, *, generated_metadata_bytes: int, name: str) -> None:
        normalized_metadata = self._require_size(generated_metadata_bytes, name)
        if normalized_metadata > self._limits.max_entry_metadata_bytes:
            raise ValidationError(
                f"Archive materialized entry metadata exceeds the limit of {self._limits.max_entry_metadata_bytes} bytes: {name}",
            )
        next_entries = self._materialized_entries + 1
        if next_entries > self._limits.max_materialized_entries:
            raise ValidationError(
                f"Archive exceeds the materialized entry limit of {self._limits.max_materialized_entries}.",
            )
        self._materialized_entries = next_entries
        if normalized_metadata:
            self._add_metadata(normalized_metadata, name)

    def add_expanded_bytes(self, additional_bytes: int, name: str) -> None:
        normalized = self._require_size(additional_bytes, name)
        next_total = self._expanded_bytes + normalized
        if next_total > self._limits.max_expanded_bytes:
            raise ValidationError(
                f"Archive expanded data exceeds the limit of {self._limits.max_expanded_bytes} bytes: {name}",
            )
        self._expanded_bytes = next_total

    def _add_metadata(self, additional_bytes: int, name: str) -> None:
        next_total = self._metadata_bytes + additional_bytes
        if next_total > self._limits.max_aggregate_metadata_bytes:
            raise ValidationError(
                f"Archive metadata exceeds the limit of {self._limits.max_aggregate_metadata_bytes} bytes: {name}",
            )
        self._metadata_bytes = next_total

    @staticmethod
    def _require_size(value: int, name: str) -> int:
        return require_non_negative_exact_int(
            value,
            type_message=f"Archive resource size must be an integer: {name}",
            range_message=f"Archive resource size must not be negative: {name}",
        )


def encoded_metadata_size(*values: str | bytes) -> int:
    total = 0
    try:
        for value in values:
            total += len(value if isinstance(value, bytes) else value.encode("utf-8"))
    except UnicodeEncodeError as exception:
        raise ValidationError("Archive metadata is not valid UTF-8.") from exception
    return total
