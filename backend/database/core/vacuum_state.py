"""SoAI - Last-vacuum-timestamp state persistence [backend/database/core/vacuum_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.filesystem.atomic_writes import atomic_write_text
from core.filesystem.open_files import open_text
from core.logging.trace import get_logger
from core.serialization.json import serialize_json_pretty_sorted_strict
from core.serialization.json_parsing import parse_json_dict
from core.timing.formatting import timestamp_to_utc_iso
from core.types.json import JSONDict
from core.validation.numbers import coerce_float_from_json

__all__ = (
    "load_last_vacuum_timestamp_from_disk",
    "persist_last_vacuum_timestamp_to_disk",
    "resolve_vacuum_state_path",
)

LOGGER_NAME = "SoAI.database.core.vacuum_state"
OPERATION_LOAD_VACUUM_TIMESTAMP = "database.core.vacuum_state.load"
OPERATION_PERSIST_VACUUM_TIMESTAMP = "database.core.vacuum_state.persist"


def resolve_vacuum_state_path(db_path: str, is_shared_memory_mode: bool) -> str | None:
    if is_shared_memory_mode:
        return None
    db_path_str = db_path.strip()
    if not db_path_str or db_path_str.startswith("file:"):
        return None
    return f"{db_path_str}.vacuum.json"


async def load_last_vacuum_timestamp_from_disk(state_path: str | None) -> float | None:
    if state_path is None:
        return None

    def _sync_read() -> float:
        with open_text(state_path, encoding="utf-8") as handle:
            payload = parse_json_dict(handle.read(), field="database vacuum state")
        timestamp = coerce_float_from_json(payload.get("last_vacuum_timestamp"), default=None)
        if timestamp is None or timestamp <= 0:
            raise ValidationError("Database vacuum timestamp must be finite and positive.")
        return timestamp

    try:
        return await asyncio.to_thread(_sync_read)
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError, OverflowError, ValidationError) as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Database vacuum timestamp could not be read; startup maintenance is due.",
            operation=OPERATION_LOAD_VACUUM_TIMESTAMP,
            level="warning",
        )
        return None


async def persist_last_vacuum_timestamp_to_disk(state_path: str | None, timestamp: float) -> bool:
    parsed = coerce_float_from_json(timestamp, default=None)
    if parsed is None or parsed <= 0:
        raise ValidationError("Database vacuum timestamp must be finite and positive.")
    if state_path is None:
        return True
    payload: JSONDict = {
        "last_vacuum_timestamp": int(parsed),
        "last_vacuum_timestamp_iso": timestamp_to_utc_iso(parsed),
    }

    def _sync_write(handle: io.TextIOBase) -> None:
        handle.write(serialize_json_pretty_sorted_strict(payload))
        handle.write("\n")

    try:
        await run_joined_thread_call(
            atomic_write_text, state_path, _sync_write, task_name="database-vacuum-timestamp"
        )
        return True
    except OSError as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Database vacuum completed but its timestamp could not be saved; maintenance is degraded.",
            operation=OPERATION_PERSIST_VACUUM_TIMESTAMP,
            level="warning",
        )
        return False
