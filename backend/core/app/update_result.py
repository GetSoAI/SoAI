"""SoAI - Application update admission result [backend/core/app/update_result.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import ValidationError
from core.tasks.identifiers import normalize_optional_task_id

if TYPE_CHECKING:
    type ApplicationUpdateOutcome = Literal["accepted", "conflict", "failed", "unavailable"]

__all__ = ("ApplicationUpdateResult",)


@dataclass(frozen=True, slots=True)
class ApplicationUpdateResult:
    outcome: ApplicationUpdateOutcome
    message: str
    task_id: str | None = None

    def __post_init__(self) -> None:
        if self.outcome == "accepted" and (
            self.task_id is None or normalize_optional_task_id(self.task_id) != self.task_id
        ):
            raise ValidationError("Accepted software update requires its canonical task identity.")
