"""SoAI - Chroma IPC worker job and response serialization [backend/mcp/storage/chroma_ipc_worker_responses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exceptions import ValidationError
from core.filesystem.atomic_writes import atomic_write_text_content
from core.filesystem.open_files import open_text
from core.hardware.reservation_claims import claim_reserved_write
from core.serialization.json import (
    normalize_for_json,
    serialize_json_compact_stable_strict,
)
from core.serialization.json_parsing import parse_json_value

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "load_job",
    "respond_error",
    "respond_ok",
)

OPERATION_RESPONSE_WRITE = "mcp.storage.chroma_worker.response.write"


def write_response_payload(
    *,
    response_path: str,
    payload: JSONDict,
    storage_manager: StorageManagerProtocol,
) -> None:
    content = serialize_json_compact_stable_strict(payload, ensure_ascii=False)
    required_bytes = len(content.encode("utf-8"))
    with (
        storage_manager.reserve_disk_space(
            path=response_path,
            required_bytes=required_bytes,
            operation=OPERATION_RESPONSE_WRITE,
            details={"response_path": response_path, "required_bytes": required_bytes},
        ) as reservation,
        claim_reserved_write(reservation, size_bytes=required_bytes),
    ):
        atomic_write_text_content(
            response_path,
            content,
            encoding="utf-8",
            errors="strict",
        )


def load_job(job_path: str) -> JSONDict:
    with open_text(job_path, mode="r", encoding="utf-8", errors="strict") as handle:
        parsed = parse_json_value(handle.read())
    if not isinstance(parsed, dict):
        raise ValidationError("Job file must contain a JSON object.")
    return parsed


def respond_error(
    *,
    request_id: str,
    response_path: str,
    exception: BaseException,
    operation: str,
    storage_manager: StorageManagerProtocol,
    details: JSONDict | None = None,
) -> None:
    error = coerce_to_soai_error(
        exception,
        operation=operation,
        details=details,
    )
    payload: JSONDict = {
        "request_id": request_id,
        "ok": False,
        "error": {
            "code": error.code,
            "message": str(error.message),
            "operation": str(error.operation or operation),
            "details": dict(error.details) if error.details else None,
        },
    }
    write_response_payload(
        response_path=response_path,
        payload=payload,
        storage_manager=storage_manager,
    )


def respond_ok(
    *,
    request_id: str,
    response_path: str,
    result: JSONValue,
    storage_manager: StorageManagerProtocol,
) -> None:
    payload: JSONDict = {"request_id": request_id, "ok": True, "result": normalize_for_json(result)}
    write_response_payload(
        response_path=response_path,
        payload=payload,
        storage_manager=storage_manager,
    )
