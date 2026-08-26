"""SoAI - Text file parser [backend/files/parsers/text.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING, override

from charset_normalizer import from_path

from core.errors.exceptions import StateError, ValidationError
from core.files.types import ParsedDocument
from core.filesystem.open_files import open_text
from core.imports.availability import require_module
from core.serialization.json_parsing import parse_json_value
from core.types.json_value import coerce_json_dict
from files.parsers.blocking_parser import BlockingParser

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "IPYNBParser",
    "TextParser",
)


def _detect_file_encoding(file_path: str) -> tuple[str, JSONDict]:
    require_module("charset_normalizer", feature="Text parsing")
    metadata: JSONDict = {}
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        metadata["empty_file"] = True
        return ("utf-8", metadata)
    detection_result = from_path(file_path)
    best_match = detection_result.best()
    if not best_match or not best_match.encoding:
        raise StateError("Unable to detect file encoding")
    detected_encoding = best_match.encoding
    encoding_lower = detected_encoding.lower()
    if encoding_lower == "utf-8-sig":
        metadata["has_bom"] = True
    elif encoding_lower != "utf-8":
        metadata["detected_encoding"] = detected_encoding
    return (detected_encoding, metadata)


def read_text_file_with_encoding_detection(
    file_path: str,
) -> tuple[str, JSONDict]:
    detected_encoding, metadata = _detect_file_encoding(file_path)
    with open_text(file_path, encoding=detected_encoding, errors="replace") as file_handle:
        content = file_handle.read()
    return (content, metadata)


class TextParser(BlockingParser):

    @override
    def parse_blocking(self, file_path: str) -> ParsedDocument:
        content, metadata = read_text_file_with_encoding_detection(file_path)
        return ParsedDocument(content=content, metadata=metadata or None)


class IPYNBParser(BlockingParser):

    @override
    def parse_blocking(self, file_path: str) -> ParsedDocument:
        def _as_text(value: JSONValue) -> str:
            if value is None:
                return ""
            if isinstance(value, str):
                return value
            if isinstance(value, list | tuple):
                return "".join(str(item) for item in value)
            return str(value)

        raw_content, metadata = read_text_file_with_encoding_detection(file_path)
        notebook = coerce_json_dict(parse_json_value(raw_content))
        if notebook is None:
            raise ValidationError("Invalid notebook format (expected JSON object)")
        content_parts: list[str] = []
        cells = notebook.get("cells", [])
        if not isinstance(cells, list):
            raise ValidationError("Invalid notebook format (cells must be a list)")
        for cell in cells:
            cell_dict = coerce_json_dict(cell)
            if cell_dict is None:
                raise ValidationError("Invalid notebook format (cell must be an object)")
            cell_type = cell_dict.get("cell_type", "")
            source = _as_text(cell_dict.get("source", []))
            if cell_type == "markdown":
                content_parts.append(source)
            elif cell_type == "code":
                content_parts.append(f"```python\n{source}\n```")
                outputs = cell_dict.get("outputs", []) or []
                if not isinstance(outputs, list):
                    raise ValidationError("Invalid notebook format (outputs must be a list)")
                output_texts: list[str] = []
                for output in outputs:
                    output_dict = coerce_json_dict(output)
                    if output_dict is None:
                        raise ValidationError("Invalid notebook format (output must be an object)")
                    output_type = output_dict.get("output_type", "")
                    if output_type == "stream":
                        text = _as_text(output_dict.get("text", ""))
                        if text.strip():
                            output_texts.append(text.strip())
                    elif output_type in {"execute_result", "display_data"}:
                        data = coerce_json_dict(output_dict.get("data")) or {}
                        if "text/plain" in data:
                            text = _as_text(data.get("text/plain"))
                            if text.strip():
                                output_texts.append(text.strip())
                    elif output_type == "error":
                        ename = output_dict.get("ename", "Error")
                        evalue = output_dict.get("evalue", "")
                        traceback_lines = output_dict.get("traceback", [])
                        rendered_traceback = _as_text(traceback_lines).strip()
                        if rendered_traceback:
                            output_texts.append(f"{ename}: {evalue}\n{rendered_traceback}")
                        else:
                            output_texts.append(f"{ename}: {evalue}")
                if output_texts:
                    joined_output_texts = "\n".join(output_texts)
                    content_parts.append(f"Output:\n```\n{joined_output_texts}\n```")
            elif cell_type == "raw" and source.strip():
                content_parts.append(f"```\n{source}\n```")
        return ParsedDocument(content=self._join_content(content_parts), metadata=metadata or None)
