"""SoAI - File move conflict errors [backend/core/files/move_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import override

from core.errors.exceptions import StateError, ValidationError
from core.types.json import JSONValue

__all__ = ("DestinationExistsError", "MoveFileCommittedError")


class DestinationExistsError(ValidationError): ...


class MoveFileCommittedError(StateError):
    def __init__(self, *, source_path: str, destination_path: str, cause: Exception) -> None:
        super().__init__(
            "File publication succeeded but move finalization failed.",
            operation="core.files.move_with_cancellation",
            details={"source_path": source_path, "destination_path": destination_path},
            cause=cause,
        )
        self.source_path = source_path
        self.destination_path = destination_path

    @override
    def __str__(self) -> str:
        return self.message

    @override
    def __getnewargs_ex__(
        self,
    ) -> tuple[
        tuple[JSONValue | BaseException | None, ...], Mapping[str, JSONValue | BaseException | None]
    ]:
        return (), {
            "source_path": self.source_path,
            "destination_path": self.destination_path,
            "cause": self.cause,
        }
