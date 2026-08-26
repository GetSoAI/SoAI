"""SoAI - Managed install marker parsing for bootstrap assets [backend/core/bootstrap/managed_install_marker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.serialization.json_parsing import parse_json_dict
from core.types.json import JSONDict

__all__ = ("read_managed_install_marker",)


def read_managed_install_marker(marker_path: str, *, field: str) -> dict[str, str] | None:
    marker_text: str | None
    try:
        with open(marker_path, encoding="utf-8", errors="strict") as handle:
            marker_text = handle.read()
    except OSError:
        marker_text = None
    if marker_text is None:
        return None

    parsed_marker: JSONDict | None
    try:
        parsed_marker = parse_json_dict(marker_text, field=field)
    except ValidationError:
        parsed_marker = None
    if parsed_marker is None:
        return None
    marker: dict[str, str] = {}
    for key, value in parsed_marker.items():
        if not isinstance(key, str) or not isinstance(value, str):
            return None
        marker[key] = value
    return marker
