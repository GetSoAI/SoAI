"""SoAI - Immutable JSON mapping type [backend/core/types/dict.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import override

from core.types.json import JSONValue
from core.types.json_value import copy_json_value

__all__ = (
    "FrozenJsonDict",
    "freeze_json_dict",
)


class FrozenJsonDict(Mapping[str, JSONValue]):
    __slots__ = ("_payload",)

    def __init__(self, payload: Mapping[str, JSONValue] | None = None) -> None:
        if payload is None:
            self._payload: dict[str, JSONValue] = {}
            return
        if isinstance(payload, FrozenJsonDict):
            self._payload = dict(payload._payload)
            return
        self._payload = {key: copy_json_value(value) for key, value in payload.items()}

    @classmethod
    def empty(cls) -> FrozenJsonDict:
        return cls({})

    @override
    def __getitem__(self, key: str) -> JSONValue:
        return copy_json_value(self._payload[key])

    @override
    def __iter__(self) -> Iterator[str]:
        return iter(self._payload)

    @override
    def __len__(self) -> int:
        return len(self._payload)


def freeze_json_dict(payload: Mapping[str, JSONValue] | None) -> FrozenJsonDict:
    if payload is None:
        return FrozenJsonDict.empty()
    if isinstance(payload, FrozenJsonDict):
        return payload
    return FrozenJsonDict(payload)
