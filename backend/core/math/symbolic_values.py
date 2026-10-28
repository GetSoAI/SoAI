"""SoAI - Symbolic math value types and argument checks [backend/core/math/symbolic_values.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sympy import (
    BasePolynomialError,
    Basic,
    Contains,
    Dict,
    Expr,
    Float,
    ImmutableMatrix,
    Integer,
    S,
    Symbol,
    nan,
    true,
)
from sympy.logic.boolalg import Boolean

from core.math.errors import MathExpressionError, build_multiple_results_error
from core.math.numeric_operators import BOOLEAN_ARITHMETIC_MESSAGE

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from core.math.function_catalog import MathFunctionSpec

    type Substitution = Mapping[Symbol, Expr] | Mapping[Basic, Basic]
    type SymbolicValue = Basic | list[SymbolicValue] | SymbolicOutcome

__all__ = (
    "LIST_VALUE_MESSAGE",
    "SYMBOLIC_FAILURES",
    "DomainRestriction",
    "SymbolicEvaluationContext",
    "SymbolicOutcome",
    "float_precision_bits",
    "index_symbolic_value",
    "require_arithmetic",
    "require_boolean_condition",
    "require_conditional_value",
    "require_bounded_integer",
    "require_expression",
    "require_expressions",
    "require_matrix",
    "require_single_value",
    "require_symbol",
)

LIST_VALUE_MESSAGE = "Lists are only allowed as function arguments, such as Matrix([[1, 2], [3, 4]]) or solve([x + y - 3, x - y - 1], [x, y])"
_OUTCOME_VALUE_MESSAGE = "A solve or limit outcome is not a number; pick a solution with s[0] when it lists finitely many"
_INDEXING_MESSAGE = "Indexing works on lists (s[0]), solutions (s[0][x]) and matrices (M[row, column]), counting from 0"
SYMBOLIC_FAILURES = (
    AttributeError,
    ValueError,
    TypeError,
    ArithmeticError,
    LookupError,
    RuntimeError,
    BasePolynomialError,
)


@dataclass(frozen=True, slots=True)
class DomainRestriction:
    term: Expr
    zero: Expr
    condition: Boolean = true
    nonfinite_bindings: tuple[tuple[Symbol, Expr], ...] | None = None

    @property
    def substitution_symbols(self) -> set[Symbol]:
        if self.nonfinite_bindings is None:
            return set()
        if not self.nonfinite_bindings:
            return self.term.free_symbols
        return {
            symbol for _original, value in self.nonfinite_bindings for symbol in value.free_symbols
        }


@dataclass(frozen=True, slots=True)
class SymbolicOutcome:
    outcome: str
    text: str
    note: str
    items: tuple[SymbolicValue, ...] = ()
    cases: tuple[tuple[str, SymbolicOutcome], ...] = ()
    item_restrictions: tuple[tuple[DomainRestriction, ...], ...] = ()
    approximate_numbers: tuple[Float, ...] = ()

    def restrictions_of(self, item: SymbolicValue) -> tuple[DomainRestriction, ...]:
        if item not in self.items or not self.item_restrictions:
            return ()
        return self.item_restrictions[self.items.index(item)]


@dataclass(frozen=True, slots=True)
class SymbolicEvaluationContext:
    variables: Mapping[str, SymbolicValue]
    functions: Mapping[str, Callable[..., SymbolicValue]]
    constants: Mapping[str, Basic]
    specs: Mapping[str, MathFunctionSpec]
    max_depth: int
    source: str
    restrictions: list[DomainRestriction] = field(default_factory=list[DomainRestriction])
    named_restrictions: dict[str, tuple[DomainRestriction, ...]] = field(
        default_factory=dict[str, tuple[DomainRestriction, ...]]
    )


def float_precision_bits(number: Float) -> int:
    _arguments, options = number.__getnewargs_ex__()
    return options["precision"]


def require_arithmetic(value: SymbolicValue) -> Expr | ImmutableMatrix:
    if isinstance(value, list):
        raise build_multiple_results_error(LIST_VALUE_MESSAGE)
    if isinstance(value, SymbolicOutcome):
        raise MathExpressionError(_OUTCOME_VALUE_MESSAGE)
    if isinstance(value, Expr | ImmutableMatrix):
        return value
    raise MathExpressionError(BOOLEAN_ARITHMETIC_MESSAGE)


def require_expression(value: SymbolicValue, *, position: int) -> Expr:
    if isinstance(value, Expr):
        return value
    raise ValueError(f"argument {position} must be an expression")


def require_single_value(value: SymbolicValue, *, position: int) -> Basic:
    if isinstance(value, list | SymbolicOutcome):
        raise ValueError(
            f"argument {position} must be a single value, not a list or a solve outcome"
        )
    return value


def require_expressions(values: Sequence[SymbolicValue]) -> list[Expr]:
    return [require_expression(value, position=index) for index, value in enumerate(values, 1)]


def require_symbol(value: SymbolicValue, *, position: int) -> Symbol:
    if isinstance(value, Symbol):
        return value
    raise ValueError(f"argument {position} must be a variable name that has no value assigned")


def require_matrix(value: SymbolicValue, *, position: int, square: bool = False) -> ImmutableMatrix:
    if isinstance(value, ImmutableMatrix):
        if square and not value.is_square:
            raise ValueError(f"argument {position} must be a square matrix")
        return value
    raise ValueError(f"argument {position} must be a matrix created with Matrix([[...], ...])")


def require_bounded_integer(value: SymbolicValue, *, position: int, maximum: int) -> int:
    if isinstance(value, Integer) and 1 <= int(value) <= maximum:
        return int(value)
    raise ValueError(f"argument {position} must be an integer from 1 to {maximum}")


def index_symbolic_value(value: SymbolicValue, indices: Sequence[SymbolicValue]) -> SymbolicValue:
    if isinstance(value, SymbolicOutcome):
        if not value.items:
            raise MathExpressionError(f"There is no finite list to index: {value.note}")
        value = list(value.items)
    if isinstance(value, list) and len(indices) == 1:
        return value[_index_position(indices[0], len(value), part="list")]
    if isinstance(value, ImmutableMatrix) and len(indices) == 2:
        rows = value.tolist()
        row = rows[_index_position(indices[0], len(rows), part="row")]
        return row[_index_position(indices[1], len(row), part="column")]
    if isinstance(value, Dict) and len(indices) == 1 and isinstance(indices[0], Symbol):
        try:
            return value[indices[0]]
        except KeyError as exception:
            raise MathExpressionError(f"The solution has no value for {indices[0]}") from exception
    if isinstance(value, Symbol):
        raise MathExpressionError(
            f"{value} has no value to index; assign it first, such as s = solve(x^2 == 4, x); s[0]"
        )
    raise MathExpressionError(_INDEXING_MESSAGE)


def _index_position(index: SymbolicValue, size: int, *, part: str) -> int:
    if not isinstance(index, Integer):
        raise MathExpressionError(f"{_INDEXING_MESSAGE}; indices must be whole numbers")
    position = int(index)
    if not -size <= position < size:
        raise MathExpressionError(
            f"{part.capitalize()} index {position} is out of range; valid indices are 0 to {size - 1}"
        )
    return position % size


def require_conditional_value(value: SymbolicValue) -> Expr | Boolean:
    if isinstance(value, Boolean) and not isinstance(value, Expr):
        return value
    arithmetic = require_arithmetic(value)
    if isinstance(arithmetic, ImmutableMatrix):
        raise MathExpressionError(
            "Conditional results must be numbers or expressions, not matrices"
        )
    return arithmetic


def require_boolean_condition(value: SymbolicValue) -> Boolean:
    if value == nan:
        return Contains(nan, S.Complexes, evaluate=False)
    if isinstance(value, Boolean) and not isinstance(value, Expr):
        return value
    raise MathExpressionError(
        "Conditions must be true/false values such as x > 0; and, or, not and if-else do not accept numbers"
    )
