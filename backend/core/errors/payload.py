"""SoAI - Public error payload serialization [backend/core/errors/payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("ErrorPublicPayload",)


@dataclass(frozen=True, slots=True)
class ErrorPublicPayload:
    code: str | int
    message: str
    param: str | None = None
    details: Mapping[str, JSONValue] | None = None
    trace_id: str | None = None

    def to_dict(self) -> JSONDict:
        payload: JSONDict = {
            "type": self.code,
            "code": self.code,
            "message": self.message,
            "param": self.param,
        }
        if self.details:
            payload["details"] = dict(self.details)
        if self.trace_id:
            payload["trace_id"] = self.trace_id
        return payload
