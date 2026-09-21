"""SoAI - Document file parser [backend/files/parsers/document.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

import requests
from tika import tika

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError
from core.files.parse_execution import raise_if_parse_cancelled
from core.files.protocols import FileParserProtocol
from core.files.types import ParsedDocument, ParseExecutionContext
from core.serialization.json import normalize_for_json
from core.serialization.json_parsing import parse_json_value
from core.types.json import is_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from files.parsers.tika_runtime import TikaRuntime

__all__ = ("TikaParser", "TikaParserDependencies")


@dataclass(frozen=True, slots=True)
class TikaParserDependencies:
    runtime: TikaRuntime

    def __post_init__(self) -> None:
        require_dependencies(owner="TikaParserDependencies", runtime=self.runtime)


class TikaParser(FileParserProtocol):
    content_separator = "\n\n"

    def __init__(self, deps: TikaParserDependencies) -> None:
        self._runtime = deps.runtime
        self._parse_lock = asyncio.Lock()

    @override
    async def parse(self, context: ParseExecutionContext) -> ParsedDocument:
        raise_if_parse_cancelled(context)
        async with self._parse_lock:
            await self._runtime.start()
            try:
                return await self._parse_once(context)
            except requests.Timeout as exception:
                raise TimeoutError("Apache Tika document parsing timed out.") from exception
            except requests.ConnectionError as exception:
                if context.remaining_seconds() <= 0:
                    raise TimeoutError("Apache Tika document parsing timed out.") from exception
                await self._runtime.restart()
                raise_if_parse_cancelled(context)
                try:
                    return await self._parse_once(context)
                except requests.Timeout as retry_exception:
                    raise TimeoutError(
                        "Apache Tika document parsing timed out."
                    ) from retry_exception

    async def _parse_once(self, context: ParseExecutionContext) -> ParsedDocument:
        remaining_seconds = context.remaining_seconds()
        if remaining_seconds <= 0:
            raise TimeoutError("Apache Tika document parsing deadline was exhausted.")
        async with asyncio.timeout(remaining_seconds):
            document = await run_joined_thread_call(
                _parse_tika_document,
                context.source_path,
                self._runtime.endpoint,
                remaining_seconds,
                context.ocr_language,
                task_name="tika-document-parse",
            )
        raise_if_parse_cancelled(context)
        return document


def _parse_tika_document(
    file_path: str,
    endpoint: str,
    timeout_seconds: float,
    ocr_language: str,
) -> ParsedDocument:
    parse_function = tika.parse1
    if not callable(parse_function):
        raise StateError("tika.parse1 is not available.")
    status_code, response_text = parse_function(
        "all",
        file_path,
        serverEndpoint=endpoint,
        headers={"X-Tika-OCRLanguage": ocr_language},
        requestOptions={"timeout": timeout_seconds},
    )
    if status_code != 200:
        raise StateError(f"Tika parser returned HTTP status {status_code}.")
    parsed = parse_json_value(response_text, field="tika response")
    if not isinstance(parsed, list):
        raise StateError("Tika parser returned a non-list response.")
    content_parts: list[str] = []
    metadata: dict[str, JSONValue] = {}
    for entry in parsed:
        if not is_json_dict(entry):
            raise StateError("Tika parser returned a non-object metadata entry.")
        content_value = entry.get("X-TIKA:content")
        if isinstance(content_value, str):
            content_parts.append(content_value)
        for key, value in entry.items():
            if key != "X-TIKA:content":
                metadata[key] = normalize_for_json(value)
    return ParsedDocument(
        content="\n\n".join(part.strip() for part in content_parts if part.strip()),
        page_count=_parse_page_count(metadata.get("xmpTPg:NPages")),
        metadata=_select_metadata(metadata),
    )


def _parse_page_count(value: JSONValue | None) -> int | None:
    if not isinstance(value, int | float | str):
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _select_metadata(metadata: dict[str, JSONValue]) -> JSONDict | None:
    selected: JSONDict = {}
    key_mapping = {
        "dc:title": "title",
        "dc:creator": "author",
        "dc:subject": "subject",
        "Content-Type": "content_type",
        "Creation-Date": "created",
        "Last-Modified": "modified",
    }
    for tika_key, selected_key in key_mapping.items():
        value = metadata.get(tika_key)
        if value:
            selected[selected_key] = normalize_for_json(value)
    return selected or None
