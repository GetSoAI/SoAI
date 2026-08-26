"""SoAI - API key response serialization [backend/features/api/runtime/api_key_serialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ()


def serialize_api_key_entry(record: Mapping[str, JSONValue]) -> JSONDict:
    serialized = dict(record)
    scopes = serialized.get("scopes")
    if isinstance(scopes, tuple):
        serialized["scopes"] = list(scopes)
    elif scopes is None:
        serialized["scopes"] = []
    return serialized
