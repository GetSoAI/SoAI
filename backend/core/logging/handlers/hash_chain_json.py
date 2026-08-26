"""SoAI - Hash-chained JSON log handler [backend/core/logging/handlers/hash_chain_json.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import logging
import os
import threading
from typing import TYPE_CHECKING, override

from core.errors.exceptions import ValidationError
from core.filesystem.open_files import open_binary, open_text
from core.logging.log_record import SoAILogRecord
from core.serialization.json import (
    normalize_for_json,
    serialize_json_compact_stable,
)
from core.serialization.json_parsing import parse_json_value
from core.timing.formatting import timestamp_to_utc_iso_no_z

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("HashChainedJSONHandler",)


class HashChainedJSONHandler(logging.Handler):
    def __init__(self, file_path: str, encoding: str = "utf-8") -> None:
        super().__init__(level=logging.INFO)
        self.file_path, self.encoding, self._lock = (
            os.path.abspath(file_path),
            encoding,
            threading.RLock(),
        )
        self._last_chain_hash = self._load_last_chain_hash()

    def _load_last_chain_hash(self) -> str | None:
        try:
            with open_binary(self.file_path, mode="rb") as file_handle:
                file_handle.seek(0, 2)
                file_size = file_handle.tell()
                if file_size == 0:
                    return None
                buffer, position = (bytearray(), file_size - 1)
                while position >= 0:
                    file_handle.seek(position)
                    byte_chunk = file_handle.read(1)
                    if byte_chunk == b"\n" and buffer:
                        break
                    if byte_chunk:
                        buffer.extend(byte_chunk)
                    position -= 1
                last_line = bytes(reversed(buffer)).decode(self.encoding, errors="replace")
                last_line_dict = parse_json_value(last_line)
                if isinstance(last_line_dict, dict):
                    chain_hash_value = last_line_dict.get("chain_hash")
                    return chain_hash_value if isinstance(chain_hash_value, str) else None
        except (
            OSError,
            ValidationError,
            ValueError,
            TypeError,
        ):
            return None
        return None

    @override
    def emit(self, record: logging.LogRecord) -> None:
        try:
            record_message = record.msg
        except AttributeError:
            record_message = None
        message: JSONValue
        normalized_record_message = normalize_for_json(record_message)
        if isinstance(normalized_record_message, dict):
            message = normalized_record_message
        else:
            message = {"message": record.getMessage()}
        entry: JSONDict = {
            "timestamp": timestamp_to_utc_iso_no_z(record.created),
            "level": record.levelname,
            "logger": record.name,
            "body": message,
        }
        trace_id = None
        if isinstance(record, SoAILogRecord):
            trace_id = record.trace_id
        elif TYPE_CHECKING:
            trace_id = None
        else:
            try:
                trace_id = record.trace_id
            except AttributeError:
                trace_id = None
        if trace_id is not None:
            entry["trace_id"] = str(trace_id)
        canonical_json = serialize_json_compact_stable(entry)
        directory_path = os.path.dirname(self.file_path)
        if directory_path and (not os.path.isdir(directory_path)):
            os.makedirs(directory_path, exist_ok=True)
        with self._lock:
            previous_hash = self._last_chain_hash or ""
            chain_hash = hashlib.sha256(
                (previous_hash + canonical_json).encode("utf-8"),
            ).hexdigest()
            entry.update(
                {
                    "prev_hash": previous_hash or None,
                    "chain_hash": chain_hash,
                },
            )
            with open_text(self.file_path, mode="a", encoding=self.encoding) as file_handle:
                file_handle.write(f"{serialize_json_compact_stable(entry)}\n")
            self._last_chain_hash = chain_hash

    @override
    def close(self) -> None:
        with self._lock:
            super().close()
