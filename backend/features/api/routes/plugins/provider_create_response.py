"""SoAI - External provider creation response projection [backend/features/api/routes/plugins/provider_create_response.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import status
from fastapi.responses import JSONResponse

from core.models.external_provider_record import ExternalProviderRecord
from core.types.json import JSONDict

__all__ = ("build_provider_create_response",)


def build_provider_create_response(
    provider_record: ExternalProviderRecord,
    validation_details: JSONDict,
) -> JSONResponse:
    discovery_skipped = provider_record.get("last_status") == "UNCHECKED"
    message = (
        "Provider created. Model discovery was skipped because STAY_OFFLINE blocks this non-local provider URL."
        if discovery_skipped
        else "Provider created and queued for model discovery."
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "message": message,
            "provider": provider_record,
            "validation": validation_details,
        },
        headers={"ETag": f'"{provider_record["revision"]}"'},
    )
