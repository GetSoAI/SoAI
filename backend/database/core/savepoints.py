"""SoAI - Atomic SQLite savepoint scopes [backend/database/core/savepoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from types import TracebackType
from typing import Literal

from core.errors.exceptions import ValidationError

__all__ = ("SQLiteSavepoint",)


class SQLiteSavepoint:
    __slots__ = ("_connection", "_name", "_rollback_requested")

    def __init__(self, connection: sqlite3.Connection, name: str) -> None:
        if (
            not name
            or not name.isascii()
            or not name.replace("_", "").isalnum()
            or name[0].isdigit()
        ):
            raise ValidationError("SQLite savepoint name is invalid.")
        self._connection = connection
        self._name = name
        self._rollback_requested = False

    def __enter__(self) -> SQLiteSavepoint:
        self._connection.execute(f"SAVEPOINT {self._name}")
        return self

    def rollback(self) -> None:
        self._rollback_requested = True

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        _ = (exception, traceback)
        try:
            if exception_type is not None or self._rollback_requested:
                self._connection.execute(f"ROLLBACK TO {self._name}")
        finally:
            self._connection.execute(f"RELEASE {self._name}")
        return False
