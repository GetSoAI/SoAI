"""SoAI - Lexical coordinates for symbolic substitution [backend/core/math/symbolic_bindings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from sympy import (
    Add,
    Basic,
    Dummy,
    Expr,
    Integral,
    Mod,
    Mul,
    Pow,
    Product,
    Sum,
    Symbol,
    default_sort_key,
    floor,
    oo,
)

from core.math.expression_limits import DISPLAY_SIGNIFICANT_DIGITS
from core.math.symbolic_precision import evaluate_symbolic_precision
from core.math.symbolic_values import require_expression

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from core.math.symbolic_values import Substitution

__all__ = (
    "compose_symbol_substitutions",
    "prepare_substitution",
    "substitute_operation_operands",
    "substitute_symbols",
)


def substitute_symbols(value: Basic, point: Substitution, *, simultaneous: bool = False) -> Basic:
    for symbol, replacement in point.items():
        if isinstance(symbol, Symbol) and isinstance(replacement, Expr):
            value = prepare_substitution(value, symbol, replacement)
    return value.subs(point, simultaneous=simultaneous)


def compose_symbol_substitutions(
    symbols: Collection[Symbol],
    bindings: Sequence[tuple[Symbol, Expr]],
    point: Substitution,
) -> tuple[tuple[Symbol, Expr], ...]:
    previous = dict(bindings)
    return tuple(
        (
            symbol,
            require_expression(substitute_symbols(previous.get(symbol, symbol), point), position=1),
        )
        for symbol in sorted(symbols, key=default_sort_key)
    )


def substitute_operation_operands(value: Expr, point: Substitution) -> Expr:
    if not isinstance(value, Add | Mul | Pow | Mod | floor):
        found = require_expression(substitute_symbols(value, point, simultaneous=True), position=1)
        if found.is_number and found.has(oo) and found not in (oo, -oo):
            return evaluate_symbolic_precision(found, DISPLAY_SIGNIFICANT_DIGITS)
        return found
    arguments = [
        substitute_operation_operands(require_expression(argument, position=1), point)
        for argument in value.args
    ]
    if isinstance(value, Add):
        return Add(*arguments)
    if isinstance(value, Mul):
        return Mul(*arguments)
    if isinstance(value, Pow):
        return Pow(arguments[0], arguments[1])
    if isinstance(value, Mod):
        return Mod(arguments[0], arguments[1])
    return floor(arguments[0])


def prepare_substitution(target: Basic, symbol: Symbol, point: Expr) -> Basic:
    if not point.free_symbols or symbol not in target.free_symbols:
        return target
    replacements: dict[Basic, Basic] = {}
    bindings = target.atoms(Integral, Sum, Product)
    names = {parameter.name for parameter in target.free_symbols | point.free_symbols}
    for original in sorted(
        bindings, key=lambda binding: len(binding.atoms(Integral, Sum, Product))
    ):
        binding = original.xreplace(replacements)
        if not isinstance(binding, Integral | Sum | Product):
            continue
        if symbol not in binding.free_symbols:
            continue
        indefinite: set[Symbol] = (
            {boundary[0] for boundary in binding.limits if len(boundary) == 1}
            if isinstance(binding, Integral)
            else set()
        )
        coordinates = set(binding.bound_symbols) | indefinite
        captured = (
            bool(coordinates & point.free_symbols)
            or any(
                isinstance(coordinate, Dummy) and str(coordinate) in names
                for coordinate in coordinates
            )
            or (
                symbol in indefinite
                and bool(point.free_symbols & (binding.free_symbols - indefinite))
            )
        )
        if captured:
            if isinstance(binding, Integral) and indefinite:
                binding = Integral(
                    binding.function,
                    *(
                        (boundary[0], boundary[0]) if len(boundary) == 1 else boundary
                        for boundary in binding.limits
                    ),
                )
            masks = {
                coordinate: _coordinate_dummy(coordinate, names)
                for coordinate in set(binding.bound_symbols) & binding.free_symbols
            }
            renamed = binding.subs(masks).xreplace(
                {
                    coordinate: _coordinate_dummy(coordinate, names)
                    for coordinate in binding.bound_symbols
                }
            )
            binding = renamed.xreplace({mask: coordinate for coordinate, mask in masks.items()})
        replacements[original] = binding
    return target.xreplace(replacements)


def _coordinate_dummy(coordinate: Symbol, names: set[str]) -> Dummy:
    name = coordinate.name
    while f"_{name}" in names:
        name = f"_{name}"
    names.add(f"_{name}")
    return Dummy(name)
