"""SoAI - Public diagnostic text redaction and bounding [backend/core/security/public_text_redaction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from functools import cache

from core.security.sensitive_detection import (
    SENSITIVE_VALUE_PATTERN_TEXTS,
    is_sensitive_key_name,
)

__all__ = (
    "PUBLIC_DIAGNOSTIC_TEXT_MAX_LENGTH",
    "bound_public_text",
    "redact_public_text_fragments",
    "sanitize_public_diagnostic_text",
)

PUBLIC_DIAGNOSTIC_TEXT_MAX_LENGTH = 400
_REDACTED_SECRET = "<redacted>"
_REDACTED_IDENTIFIER = "<redacted_id>"
_URL_PATTERN_SOURCE = r"(?i)https?://\S+"
_ENDPOINT_PATTERN_SOURCE = r"(?i)\b(?:(?:\d{1,3}\.){3}\d{1,3}|localhost)(?::\d{1,5})\b"
_UNIX_PATH_PATTERN_SOURCE = (
    r"(?i)(?<![\w.])/(?:opt|home|var|tmp|usr|etc|root|mnt|srv|app|private|proc|Users|workspace)"
    r"(?:/[A-Za-z0-9._@+-]+)+"
)
_WINDOWS_PATH_PATTERN_SOURCE = r"\b[A-Za-z]:\\[^\s'\"]+"
_SECRET_ASSIGNMENT_PATTERN_SOURCE = (
    r"(?<![\w])(?P<quote>\\?[\"'])?(?P<key>[A-Za-z][A-Za-z0-9_.-]*)"
    r"(?P<close>\\?[\"'])?(?P<separator>\s*[:=]\s*)"
)
_EMAIL_PATTERN_SOURCE = r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"
_ACCOUNT_PATTERN_SOURCE = (
    r"(?i)\b(?:acct|account|org|organization|user|proj|project|team|tenant)[-_][A-Za-z0-9-]{6,}\b"
)
_QUOTED_ACCOUNT_PATTERN_SOURCE = (
    r"(?i)\b(account|organization|org|project|tenant|user)(\s+)(['\"])[^'\"\s]{4,}\3"
)
_UUID_PATTERN_SOURCE = r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"
_LONG_NUMBER_PATTERN_SOURCE = r"\b\d{10,}\b"
_CONTROL_PATTERN_SOURCE = r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"
_INTERNAL_OBJECT_PATTERN_SOURCE = r"(?i)<[^>\r\n]{1,128}\s+object\s+at\s+0x[0-9a-f]+>"
_UNSAFE_TEXT_PATTERN_SOURCE = (
    r"(?im)<\s*(?:!doctype|html|head|body|div|span|script|style|title|table|center|h\d|p|br|a)\b"
    r"|Traceback \(most recent call last\)|File \"[^\"]+\", line \d+|^\s*at [\w.$<>]+\("
)


@cache
def _redaction_rules() -> tuple[tuple[re.Pattern[str], str], ...]:
    return (
        (re.compile(_URL_PATTERN_SOURCE), "<redacted_url>"),
        (re.compile(_ENDPOINT_PATTERN_SOURCE), "<redacted_endpoint>"),
        (re.compile(_UNIX_PATH_PATTERN_SOURCE), "<redacted_path>"),
        (re.compile(_WINDOWS_PATH_PATTERN_SOURCE), "<redacted_path>"),
        *(
            (re.compile(pattern_text), _REDACTED_SECRET)
            for pattern_text in SENSITIVE_VALUE_PATTERN_TEXTS
        ),
        (re.compile(_EMAIL_PATTERN_SOURCE), _REDACTED_SECRET),
        (re.compile(_ACCOUNT_PATTERN_SOURCE), _REDACTED_IDENTIFIER),
        (re.compile(_QUOTED_ACCOUNT_PATTERN_SOURCE), rf"\1\2\3{_REDACTED_IDENTIFIER}\3"),
        (re.compile(_UUID_PATTERN_SOURCE), _REDACTED_IDENTIFIER),
        (re.compile(_LONG_NUMBER_PATTERN_SOURCE), _REDACTED_IDENTIFIER),
        (re.compile(_INTERNAL_OBJECT_PATTERN_SOURCE), _REDACTED_SECRET),
    )


@cache
def _control_pattern() -> re.Pattern[str]:
    return re.compile(_CONTROL_PATTERN_SOURCE)


@cache
def _unsafe_text_pattern() -> re.Pattern[str]:
    return re.compile(_UNSAFE_TEXT_PATTERN_SOURCE)


def redact_public_text_fragments(text: str) -> str:
    redacted, _ = _redact_secret_assignments(text)
    for pattern, replacement in _redaction_rules():
        redacted = pattern.sub(replacement, redacted)
    return redacted


@cache
def _assignment_pattern() -> re.Pattern[str]:
    return re.compile(_SECRET_ASSIGNMENT_PATTERN_SOURCE)


def _quoted_value_end(text: str, start: int, quote: str) -> int | None:
    position = start + len(quote)
    while position < len(text):
        if text[position] == quote[-1]:
            slash_count = 0
            preceding = position - 1
            while preceding >= start and text[preceding] == "\\":
                slash_count += 1
                preceding -= 1
            if slash_count % (4 if len(quote) == 2 else 2) == len(quote) - 1:
                return position + 1
        position += 1
    return None


def _redact_secret_assignments(text: str) -> tuple[str, bool]:
    fragments: list[str] = []
    consumed = 0
    safe_boundaries = True
    assignments = list(_assignment_pattern().finditer(text))
    for assignment_index, assignment in enumerate(assignments):
        if assignment.start() < consumed or not is_sensitive_key_name(
            assignment.group("key"), include_credential_containers=True
        ):
            continue
        start = assignment.end()
        if assignment.group("quote") != assignment.group("close"):
            safe_boundaries = False
        quote_match = re.match(r"(?:[A-Za-z][A-Za-z0-9-]*[ \t]+)?(?P<quote>\\?[\"'])", text[start:])
        if text.startswith(_REDACTED_SECRET, start):
            end = start + len(_REDACTED_SECRET)
        elif quote_match is not None:
            quoted_end = _quoted_value_end(
                text, start + quote_match.start("quote"), quote_match.group("quote")
            )
            if quoted_end is None or (
                quoted_end < len(text) and text[quoted_end] not in " \t\r\n,;}])"
            ):
                safe_boundaries = False
                end = len(text)
            else:
                end = quoted_end
                if (
                    text[end : end + 1] == ","
                    and _assignment_pattern().match(text[end + 1 :].lstrip()) is None
                ):
                    safe_boundaries = False
                    end = len(text)
        else:
            authorization = "authorization" in assignment.group("key").lower()
            delimiter = re.search(r"[;}\r\n]" if authorization else r"[,;}\r\n]", text[start:])
            end = start + delimiter.start() if delimiter is not None else len(text)
            if not authorization and assignment_index + 1 < len(assignments):
                end = min(end, assignments[assignment_index + 1].start())
            if delimiter is not None and delimiter.group() == ",":
                next_assignment = _assignment_pattern().match(text[end + 1 :].lstrip())
                if next_assignment is None:
                    safe_boundaries = False
                    end = len(text)
            if (
                delimiter is not None
                and delimiter.group() in "\r\n"
                and re.match(r"\r?\n[ \t]+\S", text[end:]) is not None
                and _assignment_pattern().match(text[end:].lstrip()) is None
            ):
                safe_boundaries = False
                end = len(text)
            value = text[start:end].rstrip()
            end = start + len(value)
            if not authorization and ('"' in value or "'" in value):
                safe_boundaries = False
        fragments.extend((text[consumed:start], _REDACTED_SECRET))
        consumed = end
    fragments.append(text[consumed:])
    return "".join(fragments), safe_boundaries


def bound_public_text(text: str, *, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return f"{text[: max(max_length - 3, 1)].rstrip()}..."


def sanitize_public_diagnostic_text(
    value: str | None,
    *,
    max_length: int = PUBLIC_DIAGNOSTIC_TEXT_MAX_LENGTH,
) -> str | None:
    if not isinstance(value, str) or _unsafe_text_pattern().search(value):
        return None
    redacted, safe_boundaries = _redact_secret_assignments(value)
    if not safe_boundaries:
        return None
    collapsed = " ".join(_control_pattern().sub(" ", redacted).split())
    if not collapsed:
        return None
    return bound_public_text(redact_public_text_fragments(collapsed), max_length=max_length)
