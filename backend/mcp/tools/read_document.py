"""SoAI - MCP utility tool: read_document [backend/mcp/tools/read_document.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx2

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import InsufficientDiskSpaceError, ValidationError
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.files.temp_files import create_secure_temp_file_descriptor
from core.logging.trace import get_logger
from core.network.urls import require_absolute_http_url
from mcp.tools.argument_fields import reject_unexpected_parameters
from mcp.tools.argument_scalars import parse_int
from mcp.tools.error import MCPToolError
from mcp.tools.files_access import normalize_str, resolve_existing_file_source
from mcp.tools.offline_policy import require_url_allowed_when_offline

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict, JSONValue
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_read_document",)

LOGGER_NAME = "SoAI.mcp.tools.read_document"
OPERATION_REMOVE_TEMP_PATH = "mcp.tools.read_document.remove_temp_path"
OPERATION_CLOSE_FILE_DESCRIPTOR = "mcp.tools.read_document.close_file_descriptor"
OPERATION_REMOVE_STAGED_PATH = "mcp.tools.read_document.remove_staged_path"
_ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        "document_id",
        "file_id",
        "file_path",
        "max_chars",
        "offset_chars",
        "parse_timeout_sec",
        "url",
    },
)


async def tool_read_document(self: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    reject_unexpected_parameters(arguments, _ALLOWED_KEYS)
    file_id_value = arguments.get("file_id")
    document_id_value = arguments.get("document_id")
    file_path_value = arguments.get("file_path")
    url_value = arguments.get("url")
    file_id = normalize_str(file_id_value, field="file_id", required=False)
    document_id = normalize_str(document_id_value, field="document_id", required=False)
    file_path_arg = normalize_str(file_path_value, field="file_path", required=False)
    url = normalize_str(url_value, field="url", required=False)
    file_path_arg, url = _normalize_document_source(file_path=file_path_arg, url=url)

    provided = [value for value in (file_id, document_id, file_path_arg, url) if value is not None]
    if len(provided) != 1:
        raise MCPToolError(
            -32602,
            "Must provide exactly one of: file_id, document_id, file_path, or url",
        )

    max_chars = parse_int(
        arguments.get("max_chars"),
        default=20_000,
        min_value=1,
        max_value=200_000,
    )
    offset_chars = parse_int(
        arguments.get("offset_chars"),
        default=0,
        min_value=0,
        max_value=50_000_000,
    )
    parse_timeout_sec = parse_int(
        arguments.get("parse_timeout_sec"),
        default=30,
        min_value=1,
        max_value=600,
    )

    temp_path = None
    fetched_content_type = None
    final_url = None
    try:
        if url is not None:
            temp_path, fetched_content_type, final_url = await _download_document_url(
                self,
                url=url,
            )
            file_path_for_read = temp_path
        else:
            file_path_for_read = await resolve_existing_file_source(
                self,
                file_id=file_id,
                document_id=document_id,
                file_path=file_path_arg,
                missing_message="Must provide exactly one of: file_id, document_id, or file_path",
            )
        result = await self.document_reader.read_document_to_text(
            file_path=file_path_for_read,
            parser_registry=self.parser_registry_factory(),
            parse_timeout_sec=float(parse_timeout_sec),
            max_chars=int(max_chars),
            offset_chars=int(offset_chars),
        )
    except HTTP_RECOVERABLE_EXCEPTIONS as exception:
        raise MCPToolError(-32603, f"Failed to read document: {exception}") from exception
    finally:
        if temp_path is not None:
            try:
                os.remove(temp_path)
            except OSError as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to remove temporary downloaded document (non-critical).",
                    operation=OPERATION_REMOVE_TEMP_PATH,
                    level="debug",
                )

    metadata: dict[str, JSONValue] = dict(result.metadata or {})
    if url is not None:
        metadata["source_url"] = url
        if isinstance(final_url, str) and final_url:
            metadata["final_url"] = final_url
        if isinstance(fetched_content_type, str) and fetched_content_type:
            metadata["fetched_content_type"] = fetched_content_type
    payload: JSONDict = {
        "content": result.content,
        "parser_used": result.parser_used,
        "detected_type": result.detected_type,
        "page_count": result.page_count,
        "metadata": metadata,
        "truncated": result.truncated,
        "warnings": list(result.warnings),
        "offset_chars": result.offset_chars,
        "next_offset_chars": result.next_offset_chars,
        "total_chars": result.total_chars,
        "extraction_state": result.extraction_state.value,
    }
    if not str(result.content or "").strip():
        warnings_list = list(result.warnings)
        warnings_list.append("Extraction returned empty content.")
        payload["warnings"] = warnings_list
    return payload


def _require_http_url(url: str) -> None:
    try:
        require_absolute_http_url(url)
    except ValidationError as exception:
        raise MCPToolError(-32602, str(exception)) from exception


def _normalize_document_source(
    *,
    file_path: str | None,
    url: str | None,
) -> tuple[str | None, str | None]:
    if file_path is None or url is not None:
        return file_path, url
    if not _looks_like_remote_document_source(file_path):
        return file_path, url
    _require_http_url(file_path)
    return None, file_path


def _looks_like_remote_document_source(file_path: str) -> bool:
    parsed = urlparse(file_path)
    if not parsed.scheme:
        return False
    if "://" in file_path:
        return True
    return False


def _cleanup_staged_download_file(
    logger: LoggerProtocol,
    *,
    file_descriptor: int,
    temp_path: str,
) -> None:
    if file_descriptor != -1:
        try:
            os.close(file_descriptor)
        except OSError as close_exception:
            log_handled_exception(
                logger,
                close_exception,
                message="Failed to close staged document file descriptor (non-critical).",
                operation=OPERATION_CLOSE_FILE_DESCRIPTOR,
                level="debug",
            )
    if not temp_path:
        return
    try:
        os.remove(temp_path)
    except OSError as remove_exception:
        log_handled_exception(
            logger,
            remove_exception,
            message="Failed to remove staged document temp file (non-critical).",
            operation=OPERATION_REMOVE_STAGED_PATH,
            level="debug",
        )


def _write_download_content_to_descriptor(file_descriptor: int, content: bytes) -> None:
    open_descriptor = file_descriptor
    try:
        with os.fdopen(open_descriptor, "wb", closefd=True) as handle:
            open_descriptor = -1
            handle.write(content)
    finally:
        if open_descriptor != -1:
            os.close(open_descriptor)


async def _download_document_url(
    self: MCPUtilityToolsProtocol,
    *,
    url: str,
) -> tuple[str, str | None, str]:
    _require_http_url(url)
    await require_url_allowed_when_offline(
        self.runtime_flags,
        tool_name="read_document",
        url=url,
        capability="read_document fetch",
    )
    try:
        web_fetcher = self.web_fetcher
        if web_fetcher is None:
            raise MCPToolError(-32603, "Document fetching is unavailable.")
        fetched_by_others, fetched_content_type, final_url, _ = await web_fetcher.fetch_raw(
            url,
            offline_source=None,
            max_redirects=10,
        )
        response = httpx2.Response(
            status_code=200,
            content=fetched_by_others,
            request=httpx2.Request(method="GET", url=final_url),
        )
    except ValidationError as exception:
        raise MCPToolError(-32602, str(exception)) from exception
    file_descriptor = -1
    temp_path = ""
    try:
        reservation = self.storage_manager.reserve_disk_space(
            path=self.config.require_str("SYSTEM.PATHS.TEMP"),
            required_bytes=len(response.content),
            operation="mcp.tools.read_document.stage_url",
            details={"url": url},
        )
        with reservation:
            file_descriptor, temp_path = create_secure_temp_file_descriptor(
                directory=None,
                prefix="read_document_",
                suffix=".bin",
            )
            descriptor_to_write = file_descriptor
            file_descriptor = -1
            await uncancel_then_cleanup(
                asyncio.to_thread(
                    _write_download_content_to_descriptor,
                    descriptor_to_write,
                    response.content,
                ),
            )
        return temp_path, fetched_content_type, final_url
    except InsufficientDiskSpaceError as exception:
        _cleanup_staged_download_file(
            get_logger(LOGGER_NAME),
            file_descriptor=file_descriptor,
            temp_path=temp_path,
        )
        raise MCPToolError(-32603, str(exception)) from exception
    except OSError as exception:
        _cleanup_staged_download_file(
            get_logger(LOGGER_NAME),
            file_descriptor=file_descriptor,
            temp_path=temp_path,
        )
        raise MCPToolError(
            -32603,
            f"Failed to stage downloaded document: {exception}",
        ) from exception
