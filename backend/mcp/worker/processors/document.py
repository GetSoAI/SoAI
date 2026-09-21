"""SoAI - MCP worker uploaded document processor [backend/mcp/worker/processors/document.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.cancellation import TaskCancelledError
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.extraction_state import ExtractionState
from core.files.types import ParseExecutionContext
from core.logging.trace import get_logger
from core.media.config import resolve_media_parse_timeout
from core.timing.constants import LONG_IDLE_TIMEOUT_SEC
from core.users.ocr_preferences import resolve_user_ocr_language
from core.validation.strict_numbers import require_non_negative_int_strict
from mcp.worker.processing.durable_job_payloads import lease_identity_from_job_payload
from mcp.worker.processing.durable_job_runtime import renew_durable_processing_lease
from mcp.worker.processors.chunk_embed import process_chunk_embed_store
from mcp.worker.rag_document_status_flow import update_worker_rag_document_status

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.types.json import JSONDict
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = ("UploadedDocumentProcessingResult", "process_uploaded_document")

LOGGER_NAME = "SoAI.mcp.worker.document"
OPERATION_PARSE = "mcp.worker.document.parse"


@dataclass(frozen=True, slots=True)
class UploadedDocumentProcessingResult:
    chunks_created: int
    status_details: str | None
    warnings: tuple[str, ...]


async def process_uploaded_document(
    self: MCPWorkerProtocol,
    job: JSONDict,
    task_id: str,
    token: CancellationTokenProtocol | None = None,
) -> UploadedDocumentProcessingResult:
    document_id = job.get("document_id")
    if not isinstance(document_id, str) or not document_id:
        raise ValidationError("Job missing valid document_id for document upload")
    conv_id = job.get("conv_id")
    if not isinstance(conv_id, str) or not conv_id:
        raise ValidationError("Job missing valid conv_id for document upload")
    file_type = job.get("file_type")
    if not isinstance(file_type, str) or not file_type:
        raise ValidationError("Job missing valid file_type for document upload")
    temp_file = job.get("temp_file")
    if not isinstance(temp_file, str) or not temp_file:
        raise ValidationError("Job missing valid temp_file for document upload")
    chunk_size = job.get("chunk_size")
    if not isinstance(chunk_size, int):
        raise ValidationError("Job missing valid chunk_size for document upload")
    chunk_overlap = job.get("chunk_overlap")
    if not isinstance(chunk_overlap, int):
        raise ValidationError("Job missing valid chunk_overlap for document upload")
    embedding_model = job.get("embedding_model")
    if not isinstance(embedding_model, str) or not embedding_model:
        raise ValidationError("Job missing valid embedding_model for document upload")
    chunking_strategy = job.get("chunking_strategy")
    chunking_strategy = chunking_strategy if isinstance(chunking_strategy, str) else "token_based"
    user_id_value = job.get("user_id")
    user_id = require_non_negative_int_strict(
        user_id_value, error_message="Job missing valid user_id for document upload"
    )
    ocr_language = await resolve_user_ocr_language(self.database_users, user_id)
    file_size_value = job.get("file_size")
    if not isinstance(file_size_value, int) or file_size_value <= 0:
        raise ValidationError("Job missing valid file_size for document upload")
    job_id, lease_token = lease_identity_from_job_payload(job)
    await self.send_progress(task_id, 10, f"Parsing document ({file_type.upper()})...")
    await update_worker_rag_document_status(
        self,
        document_id=document_id,
        status="parsing",
        job_id=job_id,
        lease_token=lease_token,
    )
    parser = self.parsers.get(file_type)
    if not parser:
        raise ValidationError(
            f"No parser for file type: {file_type}",
            details={"rag_status_details": "unreadable"},
        )
    filename_value = job.get("filename")
    filename = filename_value if isinstance(filename_value, str) else f"source.{file_type}"

    async def report_parse_progress(value: float, stage: str) -> None:
        percent = min(25, max(10, 10 + round(value * 15)))
        stage_label = stage.replace("_", " ").capitalize()
        await self.send_progress(task_id, percent, f"{stage_label}...")

    parse_timeout = resolve_media_parse_timeout(
        self.config,
        filename=filename,
        mime_type="application/octet-stream",
        default_timeout_seconds=float(LONG_IDLE_TIMEOUT_SEC),
    )
    try:
        parsed = await parser.parse(
            ParseExecutionContext(
                source_path=temp_file,
                ocr_language=ocr_language,
                cancellation_token=token,
                progress_callback=report_parse_progress,
                display_name=filename,
                extraction_deadline=time.monotonic() + parse_timeout,
            ),
        )
    except TaskCancelledError:
        raise
    except ValidationError as exception:
        raise ValidationError(
            exception.message,
            details={"rag_status_details": "unreadable"},
            cause=exception,
        ) from exception
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        logger = get_logger(LOGGER_NAME)
        coerced = coerce_to_soai_error(exception, operation=OPERATION_PARSE)
        log_handled_exception(
            logger,
            coerced,
            message="Document parser failed.",
            operation=OPERATION_PARSE,
            details={"task_id": task_id, "document_id": document_id, "file_type": file_type},
            level="debug",
        )
        raise ValidationError(
            "Document parser failed.",
            details={"rag_status_details": "unreadable"},
            cause=exception,
        ) from exception
    await self.check_cancellation(task_id, "post-parse", token=token)
    if job_id and lease_token:
        await renew_durable_processing_lease(self, job_id=job_id, lease_token=lease_token)
    if not parsed.extraction_state.is_usable:
        raise ValidationError(
            "Document parser could not complete.",
            details={"rag_status_details": "unreadable"},
        )
    if not parsed.content.strip():
        error_message = parsed.metadata.get("error") if parsed.metadata else None
        if not isinstance(error_message, str) or not error_message:
            error_message = "Document contains no extractable content"
        raise ValidationError(
            error_message,
            details={"rag_status_details": "unreadable"},
        )
    await self.send_progress(task_id, 25, "Document parsed. Processing content...")
    status_details = "degraded" if parsed.extraction_state is ExtractionState.DEGRADED else None
    chunks_created = await process_chunk_embed_store(
        self,
        document_id,
        conv_id,
        parsed.content,
        chunk_size,
        chunk_overlap,
        embedding_model,
        task_id,
        user_id,
        chunking_strategy,
        token=token,
        job_id=job_id or None,
        lease_token=lease_token or None,
        status_details=status_details,
    )
    return UploadedDocumentProcessingResult(
        chunks_created=chunks_created,
        status_details=status_details,
        warnings=parsed.warnings,
    )
