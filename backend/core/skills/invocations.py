"""SoAI - Human skill invocation scanning with preserved offsets [backend/core/skills/invocations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
import shlex
from bisect import bisect_left
from collections.abc import Mapping

from core.serialization.json_parsing import parse_json_dict
from core.skills.errors import build_skill_error
from core.skills.limits import MAX_NAME_CHARACTERS
from core.skills.manifest import SKILL_NAME_PATTERN_TEXT
from core.skills.records import SkillManifest
from core.types.json import JSONDict, is_str_list

__all__ = (
    "scan_skill_invocations",
    "scan_skill_argument_bindings",
    "resolve_skill_invocation_names",
    "resolve_skill_invocation_alias",
    "project_skill_argument_bindings",
)


_PRECEDING = frozenset("([{\"'“‘")
_FOLLOWING = frozenset(".,!?:;)]}\"'”’")
_FENCE_PATTERN_TEXT = r" {0,3}(`{3,}|~{3,})(.*)"
_DELIMITERS_PATTERN_TEXT = r"`+"
_AUTOLINK_PATTERN_TEXT = r"<[^<>\r\n]*>"
_URL_PATTERN_TEXT = r"\b(?:[a-zA-Z][a-zA-Z0-9+.-]*://|www\.)[^\s<>]+"
_REFERENCE_PATTERN_TEXT = r" {0,3}\[[^\]\r\n]+\]:"


def _qualified_name_pattern() -> str:
    return rf"(?:{SKILL_NAME_PATTERN_TEXT}:)?{SKILL_NAME_PATTERN_TEXT}"


def _invocation_pattern(*, leading: bool) -> re.Pattern[str]:
    qualified_name = _qualified_name_pattern()
    expression = rf"\$({qualified_name})(?=\s|$)" if leading else rf"\$({qualified_name})"
    return re.compile(expression)


def _invocation_mask(text: str) -> bytearray:
    mask = bytearray(len(text))
    _mask_blocks(text, mask)
    _mask_inline_code(text, mask)
    _mask_links(text, mask)
    _mask_math(text, mask)
    return mask


def _leading_invocations(text: str, mask: bytearray) -> tuple[tuple[str, int], ...]:
    cursor = 0
    invocations: list[tuple[str, int]] = []
    while cursor < len(text):
        while cursor < len(text) and (
            text[cursor] in " \t" if not invocations else text[cursor].isspace()
        ):
            cursor += 1
        match = _invocation_pattern(leading=True).match(text, cursor)
        if match is None or any(mask[match.start() : match.end()]):
            break
        if any(len(part) > MAX_NAME_CHARACTERS for part in match.group(1).split(":")):
            break
        invocations.append((match.group(1), match.end()))
        cursor = match.end()
    return tuple(invocations)


def scan_skill_argument_bindings(text: str) -> tuple[tuple[str, str], ...]:
    leading = _leading_invocations(text, _invocation_mask(text))
    if not leading:
        return ()
    arguments = text[leading[-1][1] :].lstrip()
    return tuple(dict.fromkeys((name, arguments) for name, _end in leading))


def project_skill_argument_bindings(manifest: SkillManifest, arguments: str) -> JSONDict:
    try:
        positional = shlex.split(arguments, posix=True)
    except ValueError:
        return {"positional": None, "named": {}, "invalid_quotes": True}
    declaration = parse_json_dict(manifest.extensions_json).get("arguments", [])
    names = declaration.split() if isinstance(declaration, str) else declaration
    named: JSONDict = {}
    if (
        is_str_list(names)
        and len(set(names)) == len(names)
        and all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", name) for name in names)
    ):
        named = {
            name: positional[index] if index < len(positional) else ""
            for index, name in enumerate(names)
        }
    return {"positional": positional, "named": named, "invalid_quotes": False}


def scan_skill_invocations(text: str) -> tuple[str, ...]:
    mask = _invocation_mask(text)
    matches: list[tuple[int, str]] = []
    matches.extend((end - len(name), name) for name, end in _leading_invocations(text, mask))
    for match in _invocation_pattern(leading=False).finditer(text):
        start, end = match.span()
        if any(mask[start:end]) or _escaped(text, start):
            continue
        if start and not (text[start - 1].isspace() or text[start - 1] in _PRECEDING):
            continue
        if end < len(text) and not (text[end].isspace() or text[end] in _FOLLOWING):
            continue
        matches.append((start, match.group(1)))
    names: list[str] = []
    for _, name in sorted(matches):
        if (
            all(len(part) <= MAX_NAME_CHARACTERS for part in name.split(":"))
            and re.fullmatch(_qualified_name_pattern(), name)
            and name not in names
        ):
            names.append(name)
    return tuple(names)


def _exclude(mask: bytearray, start: int, end: int) -> None:
    mask[start:end] = b"\x01" * (end - start)


def _escaped(text: str, position: int) -> bool:
    backslashes = 0
    position -= 1
    while position >= 0 and text[position] == "\\":
        backslashes += 1
        position -= 1
    return backslashes % 2 == 1


def _mask_blocks(text: str, mask: bytearray) -> None:
    offset = 0
    fence_character = ""
    fence_length = 0
    for line in text.splitlines(keepends=True):
        end = offset + len(line)
        body = line.rstrip("\r\n")
        fence = re.fullmatch(_FENCE_PATTERN_TEXT, body)
        if fence_character:
            _exclude(mask, offset, end)
            if (
                fence is not None
                and fence.group(1)[0] == fence_character
                and len(fence.group(1)) >= fence_length
                and not fence.group(2).strip()
            ):
                fence_character = ""
        elif (
            body.expandtabs(4).startswith("    ")
            or body.lstrip().startswith(">")
            or re.match(_REFERENCE_PATTERN_TEXT, body)
        ):
            _exclude(mask, offset, end)
        elif fence is not None and (fence.group(1)[0] != "`" or "`" not in fence.group(2)):
            fence_character = fence.group(1)[0]
            fence_length = len(fence.group(1))
            _exclude(mask, offset, end)
        offset = end


def _mask_inline_code(text: str, mask: bytearray) -> None:
    runs = list(re.finditer(_DELIMITERS_PATTERN_TEXT, text))
    next_matching: dict[int, int] = {}
    closest_by_width: dict[int, int] = {}
    for index in range(len(runs) - 1, -1, -1):
        run = runs[index]
        if mask[run.start()]:
            continue
        width = len(run.group())
        if width in closest_by_width:
            next_matching[index] = closest_by_width[width]
        closest_by_width[width] = index
    position = 0
    while position < len(runs):
        opening = runs[position]
        if mask[opening.start()] or _escaped(text, opening.start()):
            position += 1
            continue
        closing_index = next_matching.get(position)
        if closing_index is None:
            position += 1
            continue
        _exclude(mask, opening.start(), runs[closing_index].end())
        position = closing_index + 1


def _mask_links(text: str, mask: bytearray) -> None:
    for pattern in (_AUTOLINK_PATTERN_TEXT, _URL_PATTERN_TEXT):
        for match in re.finditer(pattern, text):
            _exclude(mask, match.start(), match.end())
    position = 0
    while position < len(text) - 1:
        if text[position : position + 2] != "](" or mask[position] or _escaped(text, position):
            position += 1
            continue
        start = position + 1
        position += 2
        depth = 1
        while position < len(text) and depth:
            if not _escaped(text, position):
                if text[position] == "(":
                    depth += 1
                elif text[position] == ")":
                    depth -= 1
            position += 1
        _exclude(mask, start, position)


def _mask_math(text: str, mask: bytearray) -> None:
    closers: dict[int, list[int]] = {1: [], 2: []}
    newlines = [match.start() for match in re.finditer(r"[\r\n]", text)]
    for match in re.finditer(r"\${1,2}", text):
        start, end = match.span()
        valid_boundary = end == len(text) or text[end].isspace() or text[end] in _FOLLOWING
        if start and not text[start - 1].isspace() and valid_boundary:
            if not mask[start] and not _escaped(text, start):
                closers[end - start].append(start)
    position = 0
    while position < len(text):
        if text[position] != "$" or mask[position] or _escaped(text, position):
            position += 1
            continue
        start = position
        width = 2 if text.startswith("$$", position) else 1
        position += width
        if position == len(text) or (width == 1 and text[position].isspace()):
            continue
        closing_index = bisect_left(closers[width], position)
        if closing_index == len(closers[width]):
            continue
        closing = closers[width][closing_index]
        newline_index = bisect_left(newlines, position)
        if width == 1 and newline_index < len(newlines) and newlines[newline_index] < closing:
            continue
        _exclude(mask, start, closing + width)
        position = closing + width


def resolve_skill_invocation_names(
    texts: tuple[str, ...],
    available: Mapping[str, bool],
    aliases: Mapping[str, tuple[str, ...]] | None = None,
) -> tuple[str, ...]:
    mentions: list[str] = []
    for text in texts:
        for invocation in scan_skill_invocations(text):
            name = resolve_skill_invocation_alias(invocation, available, aliases)
            if name not in mentions:
                mentions.append(name)
    for name in mentions:
        if not available.get(name, False):
            raise build_skill_error("skill_invocation_unavailable")
    return tuple(mentions)


def resolve_skill_invocation_alias(
    name: str, available: Mapping[str, bool], aliases: Mapping[str, tuple[str, ...]] | None = None
) -> str:
    if aliases is None or name not in aliases:
        return name
    candidates = tuple(candidate for candidate in aliases[name] if candidate in available)
    if len(candidates) > 1:
        raise build_skill_error("skill_invocation_unavailable", reason="alias_ambiguous")
    if not candidates:
        raise build_skill_error("skill_invocation_unavailable")
    return candidates[0]
