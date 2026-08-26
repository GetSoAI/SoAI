"""SoAI - Typed licensing integrity failures [backend/core/licensing/errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Self

from core.errors.exceptions import StateError, ValidationError
from core.licensing.types import IntegrityFailure


class LicensingIntegrityError(ValidationError):
    @classmethod
    def for_failure(cls, failure: IntegrityFailure, message: str) -> Self:
        return cls(message, details={"failure": failure})

    @property
    def failure(self) -> IntegrityFailure:
        details = self.details
        failure = details.get("failure") if details is not None else None
        if failure == "invalid_signature":
            return "invalid_signature"
        if failure == "invalid_binding":
            return "invalid_binding"
        if failure == "invalid_contract":
            return "invalid_contract"
        raise StateError("Licensing integrity error has no valid failure classification.")


__all__ = ("LicensingIntegrityError",)
