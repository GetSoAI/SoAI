"""SoAI - Exact variable transfer to symbolic workers [backend/core/math/symbolic_requests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.math.errors import MathExpressionError
from core.math.expression_limits import MAX_INTEGER_BITS
from core.math.expression_variables import coerce_variables_map
from core.math.function_catalog import SYMBOLIC_CONSTANT_NAMES
from core.serialization.json import serialize_json_compact_stable_strict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("build_symbolic_worker_request", "read_symbolic_worker_variables")


def build_symbolic_worker_request(
    expression: str, variables: JSONValue | None, *, timeout_sec: float
) -> str:
    resolved = coerce_variables_map(variables, reserved_names=SYMBOLIC_CONSTANT_NAMES)
    return serialize_json_compact_stable_strict(
        {
            "expression": expression,
            "variables": {
                name: value for name, value in resolved.items() if isinstance(value, float)
            },
            "integer_variables": {
                name: hex(value) for name, value in resolved.items() if isinstance(value, int)
            },
            "timeout_sec": timeout_sec,
        }
    )


def read_symbolic_worker_variables(request: JSONDict) -> JSONDict:
    legacy = coerce_variables_map(request.get("variables"), reserved_names=SYMBOLIC_CONSTANT_NAMES)
    encoded = request.get("integer_variables", {})
    if not isinstance(encoded, dict):
        raise MathExpressionError("integer_variables must be an object")
    if legacy.keys() & encoded.keys():
        raise MathExpressionError("A variable must not appear in both worker variable fields")
    coerce_variables_map(
        {**dict.fromkeys(legacy, 0), **dict.fromkeys(encoded, 0)},
        reserved_names=SYMBOLIC_CONSTANT_NAMES,
    )
    decoded: JSONDict = {**legacy}
    for name, value in encoded.items():
        if (
            not isinstance(value, str)
            or not value.startswith(("0x", "-0x"))
            or len(value) > (MAX_INTEGER_BITS + 3) // 4 + 3
        ):
            raise MathExpressionError(
                "Encoded integer variables must be bounded hexadecimal values"
            )
        try:
            decoded[name] = int(value, 16)
        except ValueError as exception:
            raise MathExpressionError(
                "Encoded integer variables must be hexadecimal values"
            ) from exception
    return {**coerce_variables_map(decoded, reserved_names=SYMBOLIC_CONSTANT_NAMES)}
