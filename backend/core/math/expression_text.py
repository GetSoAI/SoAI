"""SoAI - Math expression text [backend/core/math/expression_text.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.math.errors import MathExpressionError

__all__ = (
    "normalize_expression_text",
    "rewrite_common_operator_aliases",
)

MAX_EXPRESSION_CHARS = 10000
MAX_REWRITTEN_EXPRESSION_CHARS = 12000


def normalize_expression_text(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise MathExpressionError("expression must be a non-empty string")
    if "\n" in normalized or "\r" in normalized:
        raise MathExpressionError("Newlines are not allowed in expressions")
    if len(normalized) > MAX_EXPRESSION_CHARS:
        message = f"expression exceeds max length ({MAX_EXPRESSION_CHARS} characters)"
        raise MathExpressionError(message)
    if "'" in normalized or '"' in normalized:
        raise MathExpressionError("Strings are not allowed in expressions")
    return normalized


def rewrite_common_operator_aliases(expression: str) -> str:
    rewritten = expression.replace("×", "*")
    rewritten = rewritten.replace("÷", "/")
    rewritten = rewritten.replace("−", "-")
    if "^" not in rewritten:
        return rewritten
    parts: list[str] = []
    for character in rewritten:
        if character == "^":
            parts.append("**")
        else:
            parts.append(character)
    return "".join(parts)
