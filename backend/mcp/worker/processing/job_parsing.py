"""SoAI - MCP worker durable job payload parsing [backend/mcp/worker/processing/job_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from core.types.json_value import JSONValue

__all__ = (
    "ParsedProcessingJob",
    "parse_processing_job",
)


@dataclass(frozen=True, slots=True)
class ParsedProcessingJob:
    payload: JSONDict
    task_id: str
    job_type: str
    temp_file: str | None
    job_id: str | None
    lease_token: str | None


def parse_processing_job(job: JSONValue) -> ParsedProcessingJob | None:
    job_payload = coerce_json_dict(job)
    if job_payload is None:
        return None
    temp_file_value = job_payload.get("temp_file")
    temp_file = temp_file_value if isinstance(temp_file_value, str) else None
    job_id_value = job_payload.get("job_id")
    job_id = (
        job_id_value.strip() if isinstance(job_id_value, str) and job_id_value.strip() else None
    )
    lease_token_value = job_payload.get("lease_token")
    lease_token = (
        lease_token_value.strip()
        if isinstance(lease_token_value, str) and lease_token_value.strip()
        else None
    )
    raw_task_id = job_payload.get("task_id")
    if not isinstance(raw_task_id, str) or not raw_task_id.strip():
        raise ValidationError(f"Job missing required 'task_id' field: {job_payload}")
    task_id = raw_task_id.strip()
    raw_job_type = job_payload.get("type")
    if not isinstance(raw_job_type, str) or not raw_job_type:
        raise ValidationError(f"Job missing required 'type' field: {job_payload}")
    return ParsedProcessingJob(
        payload=job_payload,
        task_id=task_id,
        job_type=raw_job_type,
        temp_file=temp_file,
        job_id=job_id,
        lease_token=lease_token,
    )
