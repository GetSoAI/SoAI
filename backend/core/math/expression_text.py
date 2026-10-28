"""SoAI - Math expression text [backend/core/math/expression_text.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from core.math.errors import MathExpressionError
from core.math.expression_limits import MAX_EXPRESSION_CHARS

__all__ = (
    "detect_unsupported_notation",
    "normalize_expression_text",
    "rewrite_common_operator_aliases",
)

_OPERATOR_ALIASES = (
    ("×", "*"),
    ("·", "*"),
    ("⋅", "*"),
    ("∗", "*"),
    ("÷", "/"),
    ("∕", "/"),
    ("−", "-"),
    ("≤", "<="),
    ("≥", ">="),
    ("≠", "!="),
)
_SUPERSCRIPT_DIGITS = "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻"
_SUPERSCRIPT_REPLACEMENTS = "0123456789+-"
_SUPERSCRIPT_RUN_PATTERN = "[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻]+"
_FACTORIAL_MARK_PATTERN = "!(?!=)"
_INLINE_MODE_PATTERN = "\\bmode\\s*=\\s*['\"]?(?:numeric|symbolic)\\b"
_UNSUPPORTED_NOTATION_HINTS = (
    ("√", "use sqrt(x)"),
    ("∛", "use cbrt(x)"),
    ("∞", "infinity is only available as oo in mode 'symbolic'"),
    ("°", "use rad(x) to convert degrees to radians"),
)


def normalize_expression_text(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise MathExpressionError("expression must be a non-empty string")
    if len(normalized) > MAX_EXPRESSION_CHARS:
        message = f"expression exceeds max length ({MAX_EXPRESSION_CHARS} characters)"
        raise MathExpressionError(message)
    try:
        normalized.encode("utf-8")
    except UnicodeEncodeError as exception:
        raise MathExpressionError("expression contains an invalid Unicode character") from exception
    lines = normalized.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    normalized = "\n".join(line.split("#", 1)[0].strip() for line in lines)
    if re.search(_INLINE_MODE_PATTERN, normalized):
        raise MathExpressionError(
            "Set mode as a separate tool argument ('mode': 'symbolic'), not inside the expression"
        )
    if "'" in normalized or '"' in normalized:
        raise MathExpressionError("Strings are not allowed in expressions")
    return normalized


def rewrite_common_operator_aliases(expression: str) -> str:
    aliases: dict[str, str | int | None] = dict(_OPERATOR_ALIASES)
    rewritten = expression.translate(str.maketrans(aliases))
    rewritten = re.sub(_SUPERSCRIPT_RUN_PATTERN, _rewrite_superscript_exponent, rewritten)
    return rewritten.replace("^", "**")


def detect_unsupported_notation(expression: str) -> None:
    for symbol, hint in _UNSUPPORTED_NOTATION_HINTS:
        if symbol in expression:
            raise MathExpressionError(f"Unsupported notation '{symbol}': {hint}")
    if re.search(_FACTORIAL_MARK_PATTERN, expression):
        raise MathExpressionError(
            "Unsupported notation '!': use factorial(n) for factorials and != for inequality"
        )


def _rewrite_superscript_exponent(match: re.Match[str]) -> str:
    exponent = match.group(0).translate(
        str.maketrans(_SUPERSCRIPT_DIGITS, _SUPERSCRIPT_REPLACEMENTS)
    )
    return f"**({exponent})"
