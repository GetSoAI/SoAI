"""SoAI - Math program parsing and statement validation [backend/core/math/expression_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ast
import keyword
import math
import re
from collections.abc import Collection
from dataclasses import dataclass

from core.math.errors import MathExpressionError, build_unsupported_element_error
from core.math.exact_integers import ensure_integer_within_budget
from core.math.expression_limits import (
    MAX_PROGRAM_NODES,
    MAX_REWRITTEN_EXPRESSION_CHARS,
    MAX_STATEMENTS,
)
from core.math.expression_text import (
    detect_unsupported_notation,
    normalize_expression_text,
    rewrite_common_operator_aliases,
)
from core.validation.integers import is_strict_int

__all__ = (
    "MathProgram",
    "MathStatement",
    "build_syntax_error_message",
    "count_nodes",
    "parse_math_program",
    "read_real_literal",
    "read_binary_chain",
    "validate_assignment_name",
)

_EXPLICIT_MULTIPLICATION_HINT = "write multiplication explicitly, e.g. 2*pi or 3*x"
_SYNTAX_HINTS = (
    ("invalid decimal literal", _EXPLICIT_MULTIPLICATION_HINT),
    ("invalid imaginary literal", _EXPLICIT_MULTIPLICATION_HINT),
)
_NUMBER_FOLLOWED_BY_NAME_PATTERN = r"(?<![\w.])(?>0[xXoObB][0-9a-fA-F_]+|(?:[0-9][0-9_]*\.?[0-9_]*|\.[0-9][0-9_]*)(?:[eE][+-]?[0-9][0-9_]*)?[jJ]?)(?=\w)(\w+)"
_MAX_REPORTED_TOKEN_CHARS = 40


@dataclass(frozen=True, slots=True)
class MathStatement:
    target: str | None
    expression: ast.expr


@dataclass(frozen=True, slots=True)
class MathProgram:
    source: str
    statements: tuple[MathStatement, ...]


def count_nodes(parsed: ast.AST) -> int:
    return sum(1 for _node in ast.walk(parsed))


def read_binary_chain(node: ast.BinOp) -> tuple[ast.expr, list[ast.BinOp]]:
    links: list[ast.BinOp] = []
    leftmost: ast.expr = node
    while isinstance(leftmost, ast.BinOp):
        links.append(leftmost)
        leftmost = leftmost.left
    links.reverse()
    return leftmost, links


def parse_math_program(
    expression: str,
    *,
    reserved_names: Collection[str],
    max_nodes: int,
) -> MathProgram:
    normalized = normalize_expression_text(expression)
    rewritten = _separate_numbers_from_keywords(rewrite_common_operator_aliases(normalized))
    if len(rewritten) > MAX_REWRITTEN_EXPRESSION_CHARS:
        raise MathExpressionError("expression exceeds max length after normalization")
    detect_unsupported_notation(rewritten)
    try:
        module = ast.parse(rewritten, mode="exec")
    except SyntaxError as exception:
        raise MathExpressionError(build_syntax_error_message(exception)) from exception
    except (RecursionError, MemoryError) as exception:
        raise MathExpressionError("Expression is too deeply nested") from exception
    if not module.body:
        raise MathExpressionError("expression must contain at least one calculation")
    if len(module.body) > MAX_STATEMENTS:
        raise MathExpressionError(
            f"Expression is too complex: at most {MAX_STATEMENTS} statements are allowed"
        )
    statements: list[MathStatement] = []
    total_nodes = 0
    for statement in module.body:
        statement_nodes = count_nodes(statement)
        if statement_nodes > max_nodes:
            raise MathExpressionError(
                f"Expression is too complex: a statement may contain at most {max_nodes} elements; pass many values as one list, such as sum([...]), or split the work into steps"
            )
        total_nodes += statement_nodes
        if total_nodes > MAX_PROGRAM_NODES:
            raise MathExpressionError(
                f"Expression is too complex: a calculation may contain at most {MAX_PROGRAM_NODES} elements; split it into separate calls"
            )
        statements.append(_build_statement(statement, reserved_names=reserved_names))
    return MathProgram(source=rewritten, statements=tuple(statements))


def read_real_literal(node: ast.Constant) -> int | float:
    value = node.value
    if isinstance(value, bool):
        raise MathExpressionError("Booleans are not allowed in expressions")
    if is_strict_int(value):
        return ensure_integer_within_budget(value, subject="Number is too large")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise MathExpressionError("Numbers must be finite")
        return value
    raise build_unsupported_element_error(node)


def validate_assignment_name(name: str, *, reserved_names: Collection[str]) -> str:
    if name.startswith("_"):
        raise MathExpressionError(f"Invalid variable name: {name}")
    if name in reserved_names:
        raise MathExpressionError(f"Variable name '{name}' is reserved")
    return name


def build_syntax_error_message(exception: SyntaxError) -> str:
    detail = str(exception.msg or "invalid syntax").strip() or "invalid syntax"
    for marker, hint in _SYNTAX_HINTS:
        if marker in detail:
            detail = f"{detail} ({hint})"
            break
    lineno_raw = exception.lineno
    offset_raw = exception.offset
    if lineno_raw is None or offset_raw is None:
        return f"Invalid expression syntax: {detail}"
    lineno = int(lineno_raw)
    offset = int(offset_raw)
    if lineno <= 0 or offset <= 0:
        return f"Invalid expression syntax: {detail}"
    text_value = exception.text
    if isinstance(text_value, str):
        snippet = text_value.strip().replace("\t", " ")
        if snippet:
            if len(snippet) > 80:
                snippet = f"{snippet[:77].rstrip()}..."
            return f"Invalid expression syntax at line {lineno}, column {offset}: {detail} (near: {snippet})"
    return f"Invalid expression syntax at line {lineno}, column {offset}: {detail}"


def _separate_numbers_from_keywords(expression: str) -> str:
    return re.sub(_NUMBER_FOLLOWED_BY_NAME_PATTERN, _split_number_from_keyword, expression)


def _split_number_from_keyword(match: re.Match[str]) -> str:
    token = match.group(0)
    name = match.group(1)
    if keyword.iskeyword(name):
        return f"{token[: -len(name)]} {name}"
    reported = token[:_MAX_REPORTED_TOKEN_CHARS]
    raise MathExpressionError(
        f"Invalid expression syntax: '{reported}' is not a valid number ({_EXPLICIT_MULTIPLICATION_HINT})"
    )


def _build_statement(
    statement: ast.stmt,
    *,
    reserved_names: Collection[str],
) -> MathStatement:
    if isinstance(statement, ast.Expr):
        return MathStatement(target=None, expression=statement.value)
    if isinstance(statement, ast.Assign):
        if len(statement.targets) != 1 or not isinstance(statement.targets[0], ast.Name):
            raise MathExpressionError(
                "Only single-name assignments are supported (name = expression)"
            )
        name = validate_assignment_name(statement.targets[0].id, reserved_names=reserved_names)
        return MathStatement(target=name, expression=statement.value)
    if isinstance(statement, ast.AugAssign) and isinstance(statement.target, ast.Name):
        name = validate_assignment_name(statement.target.id, reserved_names=reserved_names)
        current_value = ast.Name(id=name, ctx=ast.Load())
        updated_value = ast.BinOp(left=current_value, op=statement.op, right=statement.value)
        return MathStatement(target=name, expression=updated_value)
    raise MathExpressionError(
        "Unsupported statement: only calculations and assignments (name = expression) are allowed"
    )
