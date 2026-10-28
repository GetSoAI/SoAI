"""SoAI - Durable backend update identities and records [backend/core/plugins/backend_update_records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import ValidationError
from core.mutations.identifiers import require_mutation_request_id
from core.plugins.backend_variant_ids import require_backend_variant_id
from core.plugins.portable_identifiers import require_portable_plugin_identifier
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from core.validation.strict_numbers import require_optional_non_negative_int_strict
from core.validation.strings import require_bounded_trimmed_text

BACKEND_UPDATE_CONTAINMENT_REQUIRED = "containment_required"

__all__ = (
    "BACKEND_UPDATE_CONTAINMENT_REQUIRED",
    "BackendAutoAttempt",
    "BackendUpdateIdentity",
    "BackendUpdateRecord",
)

if TYPE_CHECKING:
    type BackendUpdateStatus = Literal[
        "check_pending", "current", "update_available", "check_failed"
    ]


@dataclass(frozen=True, slots=True)
class BackendUpdateIdentity:
    plugin_name: str
    package_hash: str
    configuration_hash: str | None
    backend_variant_id: str

    def __post_init__(self) -> None:
        require_portable_plugin_identifier(self.plugin_name, field_name="plugin_name")
        require_canonical_sha256_hexdigest(self.package_hash, label="package_hash")
        if self.configuration_hash is not None:
            require_canonical_sha256_hexdigest(self.configuration_hash, label="configuration_hash")
        if require_backend_variant_id(self.backend_variant_id) != self.backend_variant_id:
            raise ValidationError("Backend update variant must be canonical.")


@dataclass(frozen=True, slots=True)
class BackendAutoAttempt:
    request_id: str
    identity: BackendUpdateIdentity

    def __post_init__(self) -> None:
        require_mutation_request_id(self.request_id)


@dataclass(frozen=True, slots=True)
class BackendUpdateRecord:
    identity: BackendUpdateIdentity
    status: BackendUpdateStatus
    check_id: str
    current_version: str | None = None
    latest_version: str | None = None
    checked_at_ms: int | None = None
    failure_code: str | None = None
    auto_attempt: BackendAutoAttempt | None = None
    auto_update_failed: bool = False

    def __post_init__(self) -> None:
        if self.status not in {"check_pending", "current", "update_available", "check_failed"}:
            raise ValidationError("Invalid backend update status.")
        check_id = require_bounded_trimmed_text(
            self.check_id,
            type_message="Check generation must be text.",
            empty_message="Check generation is required.",
            max_length=255,
            max_length_message="Check generation is too long.",
        )
        if check_id != self.check_id:
            raise ValidationError("Backend check generation must be canonical.")
        for value, maximum in (
            (self.current_version, 1024),
            (self.latest_version, 1024),
            (self.failure_code, 255),
        ):
            if value is not None:
                normalized = require_bounded_trimmed_text(
                    value,
                    type_message="Backend update label must be text.",
                    empty_message="Backend update label must not be blank.",
                    max_length=maximum,
                    max_length_message="Backend update label is too long.",
                )
                if normalized != value:
                    raise ValidationError("Backend update label must be canonical.")
        require_optional_non_negative_int_strict(
            self.checked_at_ms, error_message="Backend check timestamp must be nonnegative."
        )
        if self.status in {"current", "update_available"} and self.checked_at_ms is None:
            raise ValidationError("Successful backend check requires a timestamp.")
        if (self.status == "check_failed") != (self.failure_code is not None):
            raise ValidationError("Backend check failure status and code disagree.")
        if not isinstance(self.auto_update_failed, bool):
            raise ValidationError("Automatic backend failure flag must be boolean.")
        if self.auto_attempt is None and self.auto_update_failed:
            raise ValidationError("Automatic backend failure requires an attempt.")
        if (
            self.auto_attempt is not None
            and self.auto_attempt.identity.plugin_name != self.identity.plugin_name
        ):
            raise ValidationError("Automatic attempt belongs to another plugin.")
