"""SoAI - Durable RAG job payload parsing [backend/mcp/worker/processing/durable_job_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("lease_identity_from_job_payload",)


def lease_identity_from_job_payload(job_payload: JSONDict | None) -> tuple[str | None, str | None]:
    if job_payload is None:
        return None, None
    job_id_value = job_payload.get("job_id")
    lease_token_value = job_payload.get("lease_token")
    job_id = job_id_value.strip() if isinstance(job_id_value, str) else ""
    lease_token = lease_token_value.strip() if isinstance(lease_token_value, str) else ""
    if job_id and lease_token:
        return job_id, lease_token
    return None, None
