"""SoAI - Symbolic math evaluation in an owned child process [backend/core/math/symbolic_worker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sys
from functools import partial
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.math.ast_evaluator import describe_function_failure
from core.math.errors import MathExpressionError
from core.math.expression_limits import (
    MAX_ERROR_DETAIL_CHARS,
    MAX_NESTING_DEPTH,
    MAX_STATEMENT_NODES,
    SYMBOLIC_MEMORY_LIMIT_BYTES,
)
from core.math.expression_parsing import parse_math_program
from core.math.expression_variables import coerce_variables_map
from core.math.function_catalog import build_math_function_specs
from core.math.program_evaluation import run_math_program
from core.math.symbolic_conversion import (
    build_symbolic_constants,
    convert_node,
)
from core.math.symbolic_functions import build_symbolic_functions
from core.math.symbolic_process import SYMBOLIC_MEMORY_EXIT_CODE, SYMBOLIC_MEMORY_MESSAGE
from core.math.symbolic_projection import project_symbolic_value
from core.math.symbolic_requests import read_symbolic_worker_variables
from core.math.symbolic_syntax import exact_rational
from core.math.symbolic_values import SYMBOLIC_FAILURES, SymbolicEvaluationContext
from core.runtime.process_exit_deadline import ProcessExitDeadline
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_dict
from core.system.resource_limits import limit_current_process_memory
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC
from core.validation.strict_numbers import require_finite_float_strict

if TYPE_CHECKING:
    from collections.abc import Sequence

    from core.math.expression_parsing import MathStatement
    from core.math.program_evaluation import MathEvaluation
    from core.math.symbolic_values import DomainRestriction, SymbolicValue
    from core.types.json import JSONDict, JSONValue

    type StatementRestrictions = list[tuple[DomainRestriction, ...]]

__all__ = (
    "build_symbolic_response",
    "evaluate_symbolic_expression",
    "main",
)


def evaluate_symbolic_expression(
    expression: str,
    *,
    variables: JSONValue | None,
) -> JSONDict:
    constants = build_symbolic_constants()
    scope: dict[str, SymbolicValue] = {
        name: exact_rational(value)
        for name, value in coerce_variables_map(variables, reserved_names=constants).items()
    }
    program = parse_math_program(
        expression,
        reserved_names=constants,
        max_nodes=MAX_STATEMENT_NODES,
    )
    context = SymbolicEvaluationContext(
        variables=scope,
        functions=build_symbolic_functions(),
        constants=constants,
        specs=build_math_function_specs(),
        max_depth=MAX_NESTING_DEPTH,
        source=program.source,
    )
    recorded: StatementRestrictions = []
    evaluation = run_math_program(
        program.statements,
        scope=scope,
        evaluate_statement=partial(
            _evaluate_symbolic_statement, context=context, recorded=recorded
        ),
    )
    try:
        return _project_evaluation(evaluation, program.statements, recorded)
    except SYMBOLIC_FAILURES as exception:
        raise MathExpressionError(
            "The result could not be written out; simplify it or approximate it with N(...)"
        ) from exception


def build_symbolic_response(expression: str, variables: JSONValue | None) -> JSONDict:
    try:
        projection = evaluate_symbolic_expression(expression, variables=variables)
    except MathExpressionError as exception:
        return {"status": "error", "message": exception.message[:MAX_ERROR_DETAIL_CHARS]}
    except MemoryError:
        return {"status": "error", "message": SYMBOLIC_MEMORY_MESSAGE}
    except RecursionError:
        return {
            "status": "error",
            "message": "Expression is too deeply nested or too complex for symbolic evaluation",
        }
    return {"status": "ok", **projection}


def main() -> None:
    request = parse_json_dict(
        sys.stdin.buffer.read(),
        field="symbolic evaluation request",
        reject_duplicate_keys=True,
    )
    expression = request.get("expression")
    if not isinstance(expression, str):
        raise ValidationError("Symbolic evaluation request requires an expression string.")
    timeout_sec = require_finite_float_strict(
        request.get("timeout_sec"),
        error_message="Symbolic evaluation request requires a finite timeout.",
    )
    limit_current_process_memory(
        SYMBOLIC_MEMORY_LIMIT_BYTES, exceeded_exit_code=SYMBOLIC_MEMORY_EXIT_CODE
    )
    with ProcessExitDeadline() as exit_deadline:
        exit_deadline.begin_shutdown(timeout_sec + LOCAL_IO_TIMEOUT_SEC)
        response = build_symbolic_response(expression, read_symbolic_worker_variables(request))
    sys.stdout.buffer.write(serialize_json_compact_stable_strict(response).encode("utf-8"))
    sys.stdout.buffer.flush()


def _evaluate_symbolic_statement(
    statement: MathStatement,
    *,
    context: SymbolicEvaluationContext,
    recorded: StatementRestrictions,
) -> SymbolicValue:
    context.restrictions.clear()
    try:
        value = convert_node(statement.expression, context, depth=1)
    except SYMBOLIC_FAILURES as exception:
        raise MathExpressionError(
            f"Symbolic evaluation failed: {describe_function_failure(exception)}"
        ) from exception
    restrictions = tuple(context.restrictions)
    recorded.append(restrictions)
    if statement.target is not None:
        context.named_restrictions[statement.target] = restrictions
    return value


def _project_evaluation(
    evaluation: MathEvaluation[SymbolicValue],
    statements: Sequence[MathStatement],
    recorded: StatementRestrictions,
) -> JSONDict:
    projection = project_symbolic_value(evaluation.value, None, recorded[-1])
    assigned = [
        restrictions
        for statement, restrictions in zip(statements, recorded, strict=True)
        if statement.target is not None
    ]
    if assigned:
        assignments: list[JSONValue] = [
            {
                "name": assignment.name,
                **project_symbolic_value(assignment.value, assignment.name, restrictions),
            }
            for assignment, restrictions in zip(evaluation.assignments, assigned, strict=True)
        ]
        projection["assignments"] = assignments
    return projection


if __name__ == "__main__":
    main()
