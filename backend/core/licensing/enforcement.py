"""SoAI - Runtime licensing enforcement boundary [backend/core/licensing/enforcement.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ApiError
from core.licensing.admission import LicensingOperationClass
from core.licensing.protocols import LicensingStatusProtocol

__all__ = ("LICENSING_RESTRICTED_MESSAGE", "require_ordinary_licensing")

LICENSING_RESTRICTED_MESSAGE = "Licensing recovery is required before this operation can run."


async def require_ordinary_licensing(
    licensing_status: LicensingStatusProtocol,
) -> None:
    decision = await licensing_status.admission(LicensingOperationClass.ORDINARY)
    if decision.allowed:
        return
    raise ApiError(
        LICENSING_RESTRICTED_MESSAGE,
        code="licensing_restricted",
        http_status=403,
        details={"reason": decision.reason},
    )
