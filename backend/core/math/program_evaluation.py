"""SoAI - Sequential math program evaluation and value types [backend/core/math/program_evaluation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.math.errors import MathExpressionError

if TYPE_CHECKING:
    from core.math.expression_parsing import MathStatement

    type MathValue = int | float | bool

__all__ = (
    "MathAssignment",
    "MathEvaluation",
    "run_math_program",
)


@dataclass(frozen=True, slots=True)
class MathAssignment[ValueT]:
    name: str
    value: ValueT


@dataclass(frozen=True, slots=True)
class MathEvaluation[ValueT]:
    value: ValueT
    assignments: tuple[MathAssignment[ValueT], ...]


def run_math_program[ValueT](
    statements: Sequence[MathStatement],
    *,
    scope: dict[str, ValueT],
    evaluate_statement: Callable[[MathStatement], ValueT],
) -> MathEvaluation[ValueT]:
    assignments: list[MathAssignment[ValueT]] = []
    value: ValueT | None = None
    for index, statement in enumerate(statements, 1):
        try:
            value = evaluate_statement(statement)
        except MathExpressionError as exception:
            if len(statements) == 1:
                raise
            raise MathExpressionError(
                f"Statement {index} of {len(statements)} failed, so no results were returned: {exception.message}"
            ) from exception
        if statement.target is not None:
            scope[statement.target] = value
            assignments.append(MathAssignment(name=statement.target, value=value))
    if value is None:
        raise MathExpressionError("expression must contain at least one calculation")
    return MathEvaluation(value=value, assignments=tuple(assignments))
