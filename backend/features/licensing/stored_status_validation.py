"""SoAI - Stored signed licensing-status validation [backend/features/licensing/stored_status_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.licensing.licensing_status_validation import (
    LicensingStatusBinding,
    validate_signed_licensing_status,
)
from core.licensing.protocols import LicensingRepositoryProtocol
from core.licensing.storage_records import StoredLicensingDocument
from features.licensing.stored_entitlement_validation import ValidatedStoredEntitlement


@dataclass(frozen=True, slots=True)
class ValidatedStoredStatus:
    signed_state: str | None
    verified_time_high_water_ms: int


async def validate_stored_status(
    repository: LicensingRepositoryProtocol,
    entitlement: StoredLicensingDocument,
    status: StoredLicensingDocument | None,
    validated_entitlement: ValidatedStoredEntitlement,
    *,
    now_ms: int,
) -> ValidatedStoredStatus:
    if status is None:
        return ValidatedStoredStatus(
            signed_state=None,
            verified_time_high_water_ms=validated_entitlement.verified_time_high_water_ms,
        )
    status_digest = f"sha256:{hashlib.sha256(status.canonical_content).hexdigest()}"
    if (
        status.document_type != "licensing_status"
        or status.entitlement_type is not None
        or status.entitlement_id is not None
        or not hmac.compare_digest(status.document_digest, status_digest)
    ):
        raise ValidationError("Stored licensing status record is invalid.")
    payload = validated_entitlement.payload
    license_id = payload.values.get("license_id")
    if not isinstance(license_id, str):
        raise ValidationError("Stored licensing status has no commercial license.")
    validated_status = validate_signed_licensing_status(
        status.canonical_content,
        validated_entitlement.catalog,
        LicensingStatusBinding(
            instance_id=validated_entitlement.instance_id,
            deployment_id=entitlement.deployment_id,
            license_id=license_id,
            entitlement_type=payload.entitlement_type,
            licensed_product_scope=payload.licensed_product_scope,
            current_generation=status.generation,
            current_document=status.canonical_content,
        ),
        status.issuer_authorization_snapshot,
    )
    if (
        status.license_id != license_id
        or status.deployment_id != entitlement.deployment_id
        or status.generation != validated_status.generation
        or validated_status.generation <= entitlement.generation
    ):
        raise ValidationError("Stored licensing status metadata is invalid.")
    verified_time_high_water_ms = await repository.advance_verified_time(
        max(
            int(validated_status.issued_at.timestamp() * 1000),
            int(validated_status.effective_at.timestamp() * 1000),
        )
    )
    signed_state = (
        validated_status.state
        if int(validated_status.effective_at.timestamp() * 1000) <= now_ms
        else None
    )
    return ValidatedStoredStatus(signed_state, verified_time_high_water_ms)


__all__ = ("ValidatedStoredStatus", "validate_stored_status")
