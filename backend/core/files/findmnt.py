"""SoAI - Linux findmnt JSON parsing helpers [backend/core/files/findmnt.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ProcessError, ValidationError
from core.serialization.json_parsing import parse_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("parse_findmnt_filesystems",)


def parse_findmnt_filesystems(stdout: str) -> tuple[dict[str, JSONValue], ...]:
    try:
        payload = parse_json_dict(stdout or "", field="findmnt output")
    except ValidationError as exception:
        raise ProcessError(
            "Failed to parse findmnt JSON output.",
            operation="core.files.findmnt.parse",
            details={"stdout": (stdout or "")[:2000]},
        ) from exception
    filesystems = payload.get("filesystems")
    if not isinstance(filesystems, list):
        raise ProcessError(
            "Invalid findmnt JSON output: missing filesystems.",
            operation="core.files.findmnt.parse",
        )
    return _flatten_findmnt_entries(filesystems)


def _flatten_findmnt_entries(entries: list[JSONValue]) -> tuple[dict[str, JSONValue], ...]:
    flattened: list[dict[str, JSONValue]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ProcessError(
                "Invalid findmnt JSON output: filesystem entry is not a JSON mapping.",
                operation="core.files.findmnt.parse",
            )
        if not all(isinstance(key, str) for key in entry):
            raise ProcessError(
                "Invalid findmnt JSON output: filesystem entry has a non-string key.",
                operation="core.files.findmnt.parse",
            )
        flattened.append(entry)
        children = entry.get("children")
        if children is not None and not isinstance(children, list):
            raise ProcessError(
                "Invalid findmnt JSON output: filesystem children is not a list.",
                operation="core.files.findmnt.parse",
            )
        if isinstance(children, list):
            flattened.extend(list(_flatten_findmnt_entries(children)))
    return tuple(flattened)
