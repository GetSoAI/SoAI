"""SoAI - Deterministic summary digests and merging for context compaction [backend/features/agent/runtime/context_compaction/digest.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.content_text_rendering import render_openai_content_text
from features.agent.runtime.context_compaction.history import (
    is_assistant_tool_call_message,
)
from features.agent.runtime.context_compaction.text import truncate_compaction_line
from features.agent.runtime.context_compaction.tool_digests import digest_tool_exchange
from features.agent.runtime.tool_image_relay_messages import (
    is_tool_image_relay_message,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "digest_compaction_unit",
    "merge_context_summary",
)

_MAX_SUMMARY_LINES = 64
_MAX_SUMMARY_CHARS = 6000
_MAX_ROLE_TEXT_CHARS = 120

_SECTION_ORDER: tuple[str, ...] = (
    "GOAL",
    "CONSTRAINTS",
    "DECISIONS",
    "FILES",
    "COMMANDS",
    "ERRORS",
    "STATE",
    "NEXT",
)

_SECTION_PRIORITY: tuple[str, ...] = (
    "GOAL",
    "CONSTRAINTS",
    "NEXT",
    "ERRORS",
    "DECISIONS",
    "FILES",
    "COMMANDS",
    "STATE",
)


def _resolve_section_max_lines(section: str) -> int:
    if section == "GOAL":
        return 3
    if section == "CONSTRAINTS":
        return 16
    if section == "DECISIONS":
        return 12
    if section == "FILES":
        return 16
    if section == "COMMANDS":
        return 16
    if section == "ERRORS":
        return 12
    if section == "STATE":
        return 32
    if section == "NEXT":
        return 12
    return _MAX_SUMMARY_LINES


def _strip_bullet_prefix(text: str) -> str:
    normalized = str(text or "").strip()
    if normalized.startswith("- "):
        return normalized[2:].strip()
    if normalized.startswith("* "):
        return normalized[2:].strip()
    if normalized.startswith("• "):
        return normalized[2:].strip()
    return normalized


def digest_compaction_unit(messages: list[JSONDict]) -> list[str]:
    if not messages:
        return []
    first = messages[0]
    if is_tool_image_relay_message(first):
        return []
    if first.get("role") == "user":
        lines: list[str] = []
        user_text = render_openai_content_text(first.get("content")).strip()
        if user_text:
            lines.append(
                f"user: {truncate_compaction_line(user_text, max_chars=_MAX_ROLE_TEXT_CHARS)}",
            )
        if len(messages) < 2:
            return lines
        second = messages[1]
        if is_assistant_tool_call_message(second):
            tool_calls_value = second.get("tool_calls")
            tool_calls = tool_calls_value if isinstance(tool_calls_value, list) else []
            tool_call_entries = [entry for entry in tool_calls if isinstance(entry, dict)]
            tool_messages = [message for message in messages[2:] if message.get("role") == "tool"]
            for index, tool_call in enumerate(tool_call_entries):
                tool_message = tool_messages[index] if index < len(tool_messages) else None
                lines.extend(digest_tool_exchange(tool_call, tool_message))
            assistant_content = render_openai_content_text(second.get("content")).strip()
            if assistant_content:
                lines.append(
                    f"assistant: {truncate_compaction_line(assistant_content, max_chars=_MAX_ROLE_TEXT_CHARS)}",
                )
            return lines
        if second.get("role") == "assistant":
            assistant_text = render_openai_content_text(second.get("content")).strip()
            if assistant_text:
                lines.append(
                    f"assistant: {truncate_compaction_line(assistant_text, max_chars=_MAX_ROLE_TEXT_CHARS)}",
                )
            return lines
        return lines
    if is_assistant_tool_call_message(first):
        tool_calls_value = first.get("tool_calls")
        tool_calls = tool_calls_value if isinstance(tool_calls_value, list) else []
        tool_call_entries = [entry for entry in tool_calls if isinstance(entry, dict)]
        tool_messages = [message for message in messages[1:] if message.get("role") == "tool"]
        digest_lines: list[str] = []
        for index, tool_call in enumerate(tool_call_entries):
            tool_message = tool_messages[index] if index < len(tool_messages) else None
            digest_lines.extend(digest_tool_exchange(tool_call, tool_message))
        assistant_content = render_openai_content_text(first.get("content")).strip()
        if assistant_content:
            digest_lines.append(
                f"assistant: {truncate_compaction_line(assistant_content, max_chars=_MAX_ROLE_TEXT_CHARS)}",
            )
        return digest_lines
    role_value = first.get("role")
    content_text = render_openai_content_text(first.get("content")).strip()
    if content_text:
        prefix = role_value if isinstance(role_value, str) and role_value else "message"
        return [
            f"{prefix}: {truncate_compaction_line(content_text, max_chars=_MAX_ROLE_TEXT_CHARS)}",
        ]
    return []


def merge_context_summary(existing_summary: str | None, summary_lines: list[str]) -> str | None:
    blocks = [str(existing_summary or "").strip(), "\n".join(summary_lines).strip()]
    sections: dict[str, list[str]] = {name: [] for name in _SECTION_ORDER}
    current_section = "STATE"
    for block in blocks:
        if not block:
            continue
        for raw_line in block.splitlines():
            line = truncate_compaction_line(raw_line, max_chars=240)
            if not line:
                continue
            header = _strip_bullet_prefix(line).rstrip(":").strip().upper()
            if header in sections:
                current_section = header
                continue
            normalized = _strip_bullet_prefix(line)
            if not normalized:
                continue
            sections[current_section].append(normalized)
    if not any(sections.values()):
        return None
    selected: dict[str, list[str]] = {name: [] for name in _SECTION_ORDER}
    selected_seen: set[str] = set()
    total_chars = 0
    total_lines = 0
    for section in _SECTION_PRIORITY:
        candidates = sections.get(section) or []
        if not candidates:
            continue
        limit = int(_resolve_section_max_lines(section)) or _MAX_SUMMARY_LINES
        for line in reversed(candidates):
            if line in selected_seen:
                continue
            if selected[section] and len(selected[section]) >= limit:
                break
            if total_lines >= _MAX_SUMMARY_LINES:
                break
            line_size = len(line) + 2 + (1 if total_lines else 0)
            if total_chars + line_size > _MAX_SUMMARY_CHARS:
                break
            selected[section].append(line)
            selected_seen.add(line)
            total_chars += line_size
            total_lines += 1
        selected[section].reverse()
        if total_lines >= _MAX_SUMMARY_LINES or total_chars >= _MAX_SUMMARY_CHARS:
            break
    rendered: list[str] = []
    for section in _SECTION_ORDER:
        lines = selected.get(section) or []
        if not lines:
            continue
        rendered.append(f"{section}:")
        rendered.extend(f"- {line}" for line in lines)
    return "\n".join(rendered).strip() or None
