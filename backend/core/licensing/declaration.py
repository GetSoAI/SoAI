"""SoAI - Personal-use attestation contract [backend/core/licensing/declaration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

PERSONAL_USE_ATTESTATION_REVISION = "personal-use-attestation-v1"
PERSONAL_USE_ATTESTATION_TEXT = (
    "I confirm that I will use this SoAI deployment only for personal, "
    "non-commercial purposes and not on behalf of an organization."
)

__all__ = (
    "PERSONAL_USE_ATTESTATION_REVISION",
    "PERSONAL_USE_ATTESTATION_TEXT",
)
