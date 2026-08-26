"""SoAI - WebUI attachment parse classification [backend/core/attachments/attachment_parse_classification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.attachments.attachment_parse_temp_copy import (
    copy_attachment_descriptor_to_temp_path,
)
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.document_type_detection import extract_extension, is_image_type
from core.files.extraction_state import ExtractionState
from core.files.upload_staging import cleanup_temp_file
from core.logging.trace import get_logger
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC

if TYPE_CHECKING:
    from core.files.protocols import (
        DocumentReaderProtocol,
        FileParserRegistryFactoryProtocol,
    )
    from core.files.types import DocumentReadResult

__all__ = (
    "AttachmentParseOutcome",
    "classify_attachment_descriptor_for_provider",
    "classify_attachment_for_provider",
    "read_result_outcome",
)

LOGGER_NAME = "SoAI.core.attachments.attachment_parse_classification"
OPERATION_WEBUI_ATTACHMENT_PARSE_CLASSIFY = "webui.attachment_parse.classify"


@dataclass(frozen=True, slots=True)
class AttachmentParseOutcome:
    provider_mode: str | None
    provider_text: str | None
    provider_text_truncated: bool | None
    parse_state: str
    parse_error: str | None


async def _read_document(
    *,
    document_reader: DocumentReaderProtocol,
    parser_registry_factory: FileParserRegistryFactoryProtocol,
    file_path: str,
    parse_timeout_sec: float,
    max_chars: int,
    display_name: str,
) -> DocumentReadResult:
    return await document_reader.read_document_to_text(
        file_path=file_path,
        parser_registry=parser_registry_factory(),
        parse_timeout_sec=parse_timeout_sec,
        max_chars=max_chars,
        offset_chars=0,
        display_name=display_name,
    )


def _provider_descriptor_path(descriptor: int) -> str | None:
    if os.name != "posix":
        return None
    descriptor_path = f"/proc/{os.getpid()}/fd/{descriptor}"
    if not os.path.isfile(descriptor_path):
        return None
    return descriptor_path


def _missing_file_outcome() -> AttachmentParseOutcome:
    return AttachmentParseOutcome(
        provider_mode=None,
        provider_text=None,
        provider_text_truncated=None,
        parse_state="failed",
        parse_error="Attachment file is missing from managed storage.",
    )


def _parse_failure_outcome(*, image: bool) -> AttachmentParseOutcome:
    if image:
        return AttachmentParseOutcome(
            provider_mode="image",
            provider_text=None,
            provider_text_truncated=None,
            parse_state="ready",
            parse_error=None,
        )
    return AttachmentParseOutcome(
        provider_mode=None,
        provider_text=None,
        provider_text_truncated=None,
        parse_state="failed",
        parse_error="Attachment content parsing failed.",
    )


def read_result_outcome(*, image: bool, result: DocumentReadResult) -> AttachmentParseOutcome:
    content = str(result.content or "").strip()
    if result.extraction_state in {ExtractionState.FAILED, ExtractionState.TIMED_OUT}:
        return _parse_failure_outcome(image=image)
    if image:
        return AttachmentParseOutcome(
            provider_mode="image",
            provider_text=content or None,
            provider_text_truncated=(
                bool(result.truncated or result.extraction_state is ExtractionState.DEGRADED)
                if content
                else None
            ),
            parse_state="ready",
            parse_error=None,
        )
    if content:
        return AttachmentParseOutcome(
            provider_mode="text",
            provider_text=content,
            provider_text_truncated=bool(
                result.truncated or result.extraction_state is ExtractionState.DEGRADED,
            ),
            parse_state="ready",
            parse_error=None,
        )
    return AttachmentParseOutcome(
        provider_mode="reference",
        provider_text=None,
        provider_text_truncated=None,
        parse_state="ready",
        parse_error=None,
    )


async def _classify_provider_file(
    *,
    document_reader: DocumentReaderProtocol,
    parser_registry_factory: FileParserRegistryFactoryProtocol,
    file_path: str,
    filename: str,
    mime_type: str,
    max_chars: int,
    parse_timeout_sec: float = float(INTERACTIVE_TIMEOUT_SEC),
) -> AttachmentParseOutcome:
    extension = extract_extension(filename)
    image = is_image_type(mime_type, extension)
    try:
        result = await _read_document(
            document_reader=document_reader,
            parser_registry_factory=parser_registry_factory,
            file_path=file_path,
            parse_timeout_sec=parse_timeout_sec,
            max_chars=max_chars,
            display_name=filename,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Attachment content parsing failed during provider classification.",
            operation=OPERATION_WEBUI_ATTACHMENT_PARSE_CLASSIFY,
            level="warning",
        )
        return _parse_failure_outcome(image=image)
    return read_result_outcome(image=image, result=result)


async def classify_attachment_for_provider(
    *,
    document_reader: DocumentReaderProtocol,
    parser_registry_factory: FileParserRegistryFactoryProtocol,
    file_path: str,
    filename: str,
    mime_type: str,
    max_chars: int,
    parse_timeout_sec: float = float(INTERACTIVE_TIMEOUT_SEC),
) -> AttachmentParseOutcome:
    if not os.path.isfile(file_path):
        return _missing_file_outcome()
    return await _classify_provider_file(
        document_reader=document_reader,
        parser_registry_factory=parser_registry_factory,
        file_path=file_path,
        filename=filename,
        mime_type=mime_type,
        parse_timeout_sec=parse_timeout_sec,
        max_chars=max_chars,
    )


async def classify_attachment_descriptor_for_provider(
    *,
    document_reader: DocumentReaderProtocol,
    parser_registry_factory: FileParserRegistryFactoryProtocol,
    descriptor: int,
    filename: str,
    mime_type: str,
    max_chars: int,
    parse_timeout_sec: float = float(INTERACTIVE_TIMEOUT_SEC),
) -> AttachmentParseOutcome:
    descriptor_path = _provider_descriptor_path(descriptor)
    if descriptor_path is not None:
        return await _classify_provider_file(
            document_reader=document_reader,
            parser_registry_factory=parser_registry_factory,
            file_path=descriptor_path,
            filename=filename,
            mime_type=mime_type,
            parse_timeout_sec=parse_timeout_sec,
            max_chars=max_chars,
        )
    temp_path = copy_attachment_descriptor_to_temp_path(
        descriptor=descriptor,
        filename=filename,
    )
    try:
        return await _classify_provider_file(
            document_reader=document_reader,
            parser_registry_factory=parser_registry_factory,
            file_path=temp_path,
            filename=filename,
            mime_type=mime_type,
            parse_timeout_sec=parse_timeout_sec,
            max_chars=max_chars,
        )
    finally:
        await cleanup_temp_file(temp_path)
