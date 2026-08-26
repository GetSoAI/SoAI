"""SoAI - ARIA snapshot line parsing helpers [backend/mcp/tools/browser/aria_snapshot_lines.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from collections.abc import Iterable

from core.types.json import JSONDict

__all__ = (
    "filter_snapshot_refs_by_roles",
    "filter_snapshot_text_by_roles",
    "parse_aria_snapshot_role_and_name",
)

ROLE_AND_NAME_PATTERN_TEXT = r'^\s*[-*]?\s*([a-zA-Z][a-zA-Z0-9_-]*)\s*:?\s+"([^"]+)"'


def parse_aria_snapshot_role_and_name(line: str) -> tuple[str, str] | None:
    match = re.match(ROLE_AND_NAME_PATTERN_TEXT, str(line or ""))
    if match is None:
        return None
    role_raw = match.group(1)
    name_raw = match.group(2)
    role = str(role_raw or "").strip()
    name = str(name_raw or "").strip()
    if not role or not name:
        return None
    return (role, name)


def filter_snapshot_text_by_roles(snapshot_text: str, *, allowed_roles: set[str]) -> str:
    lines: list[str] = []
    for line in str(snapshot_text or "").splitlines():
        parsed = parse_aria_snapshot_role_and_name(line)
        if parsed is None:
            continue
        role, _name = parsed
        if role.strip().lower() in allowed_roles:
            lines.append(line)
    return "\n".join(lines)


def filter_snapshot_refs_by_roles(
    refs: Iterable[JSONDict],
    *,
    allowed_roles: set[str],
) -> list[JSONDict]:
    filtered: list[JSONDict] = []
    for item in refs:
        role_raw = item.get("role")
        role = str(role_raw or "").strip().lower()
        if not role:
            continue
        if role in allowed_roles:
            filtered.append(item)
    return filtered
