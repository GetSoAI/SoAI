"""SoAI - Exact symbolic matrix operations and rank certificates [backend/core/math/symbolic_matrices.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from itertools import combinations
from math import comb
from typing import TYPE_CHECKING

from sympy import (
    Add,
    Expr,
    ImmutableMatrix,
    Integer,
    default_sort_key,
    fraction,
    groebner,
    simplify,
    together,
)
from sympy.matrices.exceptions import NonInvertibleMatrixError

from core.math.errors import MathDomainError
from core.math.symbolic_values import require_expression, require_matrix

if TYPE_CHECKING:
    from core.math.symbolic_values import SymbolicValue

__all__ = ("build_symbolic_matrix_operations",)

_MAX_RANK_MINORS = 400


def build_symbolic_matrix_operations() -> dict[str, Callable[..., SymbolicValue]]:
    return {
        "Matrix": _matrix,
        "det": _determinant,
        "inv": _inverse,
        "transpose": _transpose,
        "rank": _rank,
        "eigenvals": _eigenvalues,
    }


def _matrix(rows: SymbolicValue) -> ImmutableMatrix:
    if not isinstance(rows, list) or not rows:
        raise ValueError("argument 1 must be a non-empty list of rows such as [[1, 2], [3, 4]]")
    if all(isinstance(row, list) for row in rows):
        return ImmutableMatrix(
            [[require_expression(item, position=1) for item in _row(row)] for row in rows]
        )
    return ImmutableMatrix([require_expression(item, position=1) for item in rows])


def _row(row: SymbolicValue) -> list[SymbolicValue]:
    if isinstance(row, list):
        return row
    raise ValueError("argument 1 must contain only rows or only values")


def _determinant(value: SymbolicValue) -> Expr:
    return require_matrix(value, position=1, square=True).det()


def _inverse(value: SymbolicValue) -> ImmutableMatrix:
    matrix = require_matrix(value, position=1, square=True)
    try:
        return matrix.inv()
    except NonInvertibleMatrixError as exception:
        raise MathDomainError("The matrix is singular and cannot be inverted") from exception


def _transpose(value: SymbolicValue) -> ImmutableMatrix:
    return require_matrix(value, position=1).T


def _rank(value: SymbolicValue) -> Integer:
    matrix = require_matrix(value, position=1)
    rank = matrix.rank()
    if rank and matrix.free_symbols and not _has_nonzero_minor(matrix.tolist(), rank):
        raise ValueError(
            "the rank depends on the values of the symbols or could not be proved constant; substitute values for them first"
        )
    return Integer(rank)


def _has_nonzero_minor(rows: list[list[Expr]], size: int) -> bool:
    if comb(len(rows), size) * comb(len(rows[0]), size) > _MAX_RANK_MINORS:
        return False
    minors = [
        ImmutableMatrix([[rows[row][column] for column in columns] for row in chosen]).det()
        for chosen in combinations(range(len(rows)), size)
        for columns in combinations(range(len(rows[0])), size)
    ]
    if any(minor.is_zero is False for minor in minors):
        return True
    certificate = simplify(Add(*(minor**2 for minor in minors)))
    if isinstance(certificate, Expr) and certificate.is_zero is False:
        return True
    numerators = [fraction(together(minor))[0] for minor in minors]
    if any(numerator.is_zero is False for numerator in numerators):
        return True
    symbols = sorted(
        {symbol for numerator in numerators for symbol in numerator.free_symbols},
        key=default_sort_key,
    )
    return (
        bool(symbols)
        and all(numerator.is_polynomial(*symbols) for numerator in numerators)
        and (groebner(numerators, *symbols).contains(Integer(1)))
    )


def _eigenvalues(value: SymbolicValue) -> list[SymbolicValue]:
    matrix = require_matrix(value, position=1, square=True)
    eigenvalues = matrix.eigenvals()
    return [
        eigenvalue
        for eigenvalue in sorted(eigenvalues, key=default_sort_key)
        for _repetition in range(int(eigenvalues[eigenvalue]))
    ]
