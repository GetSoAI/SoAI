"""SoAI - Current controlling license acceptance guard [backend/core/licensing/license_acceptance.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.licensing.storage_records import LicensingWizardDraft


def require_current_license_acceptance(
    draft: LicensingWizardDraft,
    controlling_license_fingerprint: str,
) -> None:
    if (
        draft.get("accepted_license_fingerprint") != controlling_license_fingerprint
        or draft.get("accepted_license_at_ms") is None
    ):
        raise ValidationError("The current controlling license must be accepted.")


__all__ = ("require_current_license_acceptance",)
