"""SoAI - Conversion of vetted math syntax trees to sympy values [backend/core/math/symbolic_conversion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ast
from dataclasses import replace
from typing import TYPE_CHECKING

from sympy import (
    And,
    Basic,
    E,
    Expr,
    I,
    Not,
    Or,
    Piecewise,
    Symbol,
    false,
    nan,
    oo,
    pi,
    true,
)
from sympy.logic.boolalg import Boolean

from core.math.ast_evaluator import describe_function_failure, read_math_call
from core.math.errors import (
    MathDomainError,
    MathExpressionError,
    build_multiple_results_error,
    build_unsupported_element_error,
    ensure_supported_comparisons,
)
from core.math.expression_parsing import read_binary_chain
from core.math.function_catalog import (
    MATH_MODE_SYMBOLIC,
    resolve_math_name,
    validate_math_call_arity,
)
from core.math.symbolic_domain import extend_restrictions, record_restriction, region_restriction
from core.math.symbolic_operation_domains import (
    BOUNDED_BODY_FUNCTIONS,
    bound_body_reachability,
    record_comparison_restrictions,
    record_function_restriction,
    record_operator_restriction,
)
from core.math.symbolic_operators import (
    apply_symbolic_binary_operator,
    apply_symbolic_comparison,
)
from core.math.symbolic_restricted_calls import call_with_restrictions
from core.math.symbolic_simplification_domains import record_cancelled_operands
from core.math.symbolic_syntax import read_symbolic_literal, validate_symbolic_structure
from core.math.symbolic_undefined import absorb_undefined
from core.math.symbolic_values import (
    LIST_VALUE_MESSAGE,
    SYMBOLIC_FAILURES,
    DomainRestriction,
    SymbolicEvaluationContext,
    SymbolicOutcome,
    index_symbolic_value,
    require_arithmetic,
    require_boolean_condition,
    require_conditional_value,
)

if TYPE_CHECKING:
    from core.math.symbolic_values import SymbolicValue

__all__ = (
    "build_symbolic_constants",
    "convert_node",
)


def build_symbolic_constants() -> dict[str, Basic]:
    return {"pi": pi, "e": E, "tau": 2 * pi, "π": pi, "τ": 2 * pi, "I": I, "oo": oo}


def convert_node(node: ast.AST, context: SymbolicEvaluationContext, *, depth: int) -> SymbolicValue:
    if depth > context.max_depth:
        raise MathExpressionError("Expression is too deeply nested")
    if isinstance(node, ast.Constant):
        return read_symbolic_literal(node, source=context.source)
    if isinstance(node, ast.Name):
        return _resolve_name(node.id, context)
    if isinstance(node, ast.UnaryOp):
        return _convert_unary(node, context, depth=depth)
    if isinstance(node, ast.BinOp):
        leftmost, links = read_binary_chain(node)
        value = convert_node(leftmost, context, depth=depth + 1)
        for link in links:
            right = convert_node(link.right, context, depth=depth + 1)
            record_operator_restriction(context.restrictions, link.op, value, right)
            result = apply_symbolic_binary_operator(link.op, value, right)
            record_cancelled_operands(context.restrictions, link.op, value, right, result)
            value = absorb_undefined([value, right], result)
        return value
    if isinstance(node, ast.Compare):
        return _convert_comparison(node, context, depth=depth)
    if isinstance(node, ast.BoolOp):
        return _convert_boolean_operation(node, context, depth=depth)
    if isinstance(node, ast.IfExp):
        condition = require_boolean_condition(convert_node(node.test, context, depth=depth + 1))
        if condition == true:
            return require_conditional_value(convert_node(node.body, context, depth=depth + 1))
        if condition == false:
            return require_conditional_value(convert_node(node.orelse, context, depth=depth + 1))
        body = require_conditional_value(
            _convert_guarded(node.body, context, depth=depth, guard=condition)
        )
        alternative = require_conditional_value(
            _convert_guarded(node.orelse, context, depth=depth, guard=Not(condition))
        )
        if body == nan and not isinstance(alternative, Expr):
            body = require_boolean_condition(body)
        if alternative == nan and not isinstance(body, Expr):
            alternative = require_boolean_condition(alternative)
        if isinstance(body, Expr) and isinstance(alternative, Expr):
            return Piecewise((body, condition), (alternative, true))
        if isinstance(body, Expr) or isinstance(alternative, Expr):
            raise MathExpressionError(
                "Conditional branches must both be expressions or both be conditions"
            )
        return Or(And(condition, body), And(Not(condition), alternative))
    if isinstance(node, ast.Call):
        return _convert_call(node, context, depth=depth)
    if isinstance(node, ast.Subscript):
        return _convert_subscript(node, context, depth=depth)
    if isinstance(node, ast.List):
        raise build_multiple_results_error(LIST_VALUE_MESSAGE)
    raise build_unsupported_element_error(node)


def _convert_boolean_operation(
    node: ast.BoolOp, context: SymbolicEvaluationContext, *, depth: int
) -> Boolean:
    is_or = isinstance(node.op, ast.Or)
    deciding = true if is_or else false
    operands: list[Boolean] = []
    for operand_node in node.values:
        reached = And(*(Not(earlier) for earlier in operands)) if is_or else And(*operands)
        operand = require_boolean_condition(
            _convert_guarded(operand_node, context, depth=depth, guard=reached)
        )
        if operand == deciding:
            return deciding
        operands.append(operand)
    return Or(*operands) if is_or else And(*operands)


def _convert_guarded(
    node: ast.expr, context: SymbolicEvaluationContext, *, depth: int, guard: Boolean
) -> SymbolicValue:
    if guard == true:
        return convert_node(node, context, depth=depth + 1)
    branch_context = replace(context, restrictions=[])
    try:
        value = convert_node(node, branch_context, depth=depth + 1)
    except MathDomainError:
        validate_symbolic_structure(node, branch_context, depth=depth + 1)
        record_restriction(context.restrictions, region_restriction(guard))
        return nan
    extend_restrictions(context.restrictions, branch_context.restrictions, condition=guard)
    return value


def _convert_subscript(
    node: ast.Subscript, context: SymbolicEvaluationContext, *, depth: int
) -> SymbolicValue:
    index_nodes = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
    if any(isinstance(index, ast.Slice) for index in index_nodes):
        raise MathExpressionError(
            "Slices are not supported; index one element at a time, such as s[0]"
        )
    value = convert_node(node.value, context, depth=depth + 1)
    indices = [convert_node(index, context, depth=depth + 1) for index in index_nodes]
    item = index_symbolic_value(value, indices)
    if isinstance(value, SymbolicOutcome):
        extend_restrictions(context.restrictions, value.restrictions_of(item))
    return item


def _resolve_name(name: str, context: SymbolicEvaluationContext) -> SymbolicValue:
    value = resolve_math_name(
        name,
        variables=context.variables,
        constants=context.constants,
        specs=context.specs,
    )
    extend_restrictions(context.restrictions, context.named_restrictions.get(name, ()))
    return Symbol(name) if value is None else value


def _convert_unary(
    node: ast.UnaryOp,
    context: SymbolicEvaluationContext,
    *,
    depth: int,
) -> Basic:
    operand = convert_node(node.operand, context, depth=depth + 1)
    if isinstance(node.op, ast.Not):
        return Not(require_boolean_condition(operand))
    value = require_arithmetic(operand)
    if isinstance(node.op, ast.UAdd):
        return value
    if isinstance(node.op, ast.USub):
        return -value
    raise build_unsupported_element_error(node.op)


def _convert_comparison(
    node: ast.Compare,
    context: SymbolicEvaluationContext,
    *,
    depth: int,
) -> Boolean:
    ensure_supported_comparisons(node)
    left = require_arithmetic(convert_node(node.left, context, depth=depth + 1))
    relations: list[Boolean] = []
    for operator, comparator in zip(node.ops, node.comparators, strict=True):
        right = require_arithmetic(
            _convert_guarded(comparator, context, depth=depth, guard=And(*relations))
        )
        comparison_domains: list[DomainRestriction] = []
        record_comparison_restrictions(comparison_domains, operator, left, right)
        extend_restrictions(context.restrictions, comparison_domains, condition=And(*relations))
        relation = apply_symbolic_comparison(operator, left, right)
        if relation == false:
            return false
        relations.append(relation)
        left = right
    return relations[0] if len(relations) == 1 else And(*relations)


def _convert_call(
    node: ast.Call, context: SymbolicEvaluationContext, *, depth: int
) -> SymbolicValue:
    spec, argument_nodes = read_math_call(node, mode=MATH_MODE_SYMBOLIC, specs=context.specs)
    name = spec.name
    bounded = name in BOUNDED_BODY_FUNCTIONS and len(argument_nodes) == 4
    indices = (1, 2, 3, 0) if bounded else range(len(argument_nodes))
    arguments: list[SymbolicValue] = [nan] * len(argument_nodes)
    domains: list[list[DomainRestriction]] = [[] for _argument in argument_nodes]
    for index in indices:
        argument_context = replace(context, restrictions=[])
        if bounded and index == 0:
            guard = bound_body_reachability(name, arguments)
            arguments[index] = _convert_guarded(
                argument_nodes[index], argument_context, depth=depth, guard=guard
            )
        else:
            arguments[index] = _convert_argument(
                argument_nodes[index], argument_context, depth=depth + 1
            )
        domains[index] = argument_context.restrictions
    if (
        spec.accepts_value_list
        and len(arguments) == 1
        and isinstance(arguments[0], list)
        and not isinstance(node.args[0], ast.List)
    ):
        arguments = arguments[0]
        validate_math_call_arity(spec, len(arguments))
    introduced: list[DomainRestriction] = []
    function = context.functions[name]
    try:
        record_function_restriction(introduced, name, arguments)
        return call_with_restrictions(
            name, function, arguments, context.restrictions, domains, introduced
        )
    except MathDomainError as exception:
        raise MathDomainError(
            f"Invalid call to {spec.signature}: {exception.message}"
        ) from exception
    except SYMBOLIC_FAILURES as exception:
        raise MathExpressionError(
            f"Invalid call to {spec.signature}: {describe_function_failure(exception)}"
        ) from exception


def _convert_argument(
    node: ast.expr,
    context: SymbolicEvaluationContext,
    *,
    depth: int,
) -> SymbolicValue:
    if depth > context.max_depth:
        raise MathExpressionError("Expression is too deeply nested")
    if isinstance(node, ast.List):
        return [_convert_argument(element, context, depth=depth + 1) for element in node.elts]
    return convert_node(node, context, depth=depth)
