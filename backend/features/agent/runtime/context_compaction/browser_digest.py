"""SoAI - Browser digest extraction for context compaction [backend/features/agent/runtime/context_compaction/browser_digest.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("digest_browser_snapshot_payload",)

_CURRENCY_PATTERN = r"(€|\$|£|¥|₹)"
_ASIN_PATTERN = r"\bB0[A-Z0-9]{8}\b"
_INTEREST_WINDOW_RADIUS = 2
_MAX_DIGEST_LINE_CHARS = 240


def _normalize_snapshot_line(line: str) -> str:
    return " ".join(str(line or "").strip().split())


def _truncate_line(text: str) -> str:
    normalized = str(text or "").strip()
    if len(normalized) <= _MAX_DIGEST_LINE_CHARS:
        return normalized
    return f"{normalized[: _MAX_DIGEST_LINE_CHARS - 1].rstrip()}…"


def _dedupe_preserve_order(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for line in lines:
        normalized = _truncate_line(line)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _is_interesting_snapshot_line(line: str) -> bool:
    normalized = _normalize_snapshot_line(line)
    if not normalized:
        return False
    if re.search(_CURRENCY_PATTERN, normalized) is not None:
        return True
    if re.search(_ASIN_PATTERN, normalized) is not None:
        return True
    if "/dp/" in normalized or "/gp/product/" in normalized:
        return True
    return False


def _collect_interesting_windows(lines: list[str]) -> list[tuple[int, int]]:
    windows: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        if not _is_interesting_snapshot_line(line):
            continue
        start = max(0, index - _INTEREST_WINDOW_RADIUS)
        end = min(len(lines), index + _INTEREST_WINDOW_RADIUS + 1)
        if windows and start <= windows[-1][1]:
            windows[-1] = (windows[-1][0], max(windows[-1][1], end))
            continue
        windows.append((start, end))
    return windows


def _is_contextual_snapshot_line(line: str) -> bool:
    normalized = _normalize_snapshot_line(line)
    if not normalized:
        return False
    if _is_interesting_snapshot_line(normalized):
        return True
    if "/url:" in normalized:
        return True
    if 'link "' in normalized:
        return True
    if "prezzo" in normalized.lower():
        return True
    if "product" in normalized.lower():
        return True
    return False


def digest_browser_snapshot_payload(payload: JSONDict) -> list[str]:
    lines: list[str] = []
    title_value = payload.get("title")
    url_value = payload.get("url")
    truncated_value = payload.get("truncated")
    metadata_parts: list[str] = []
    if isinstance(title_value, str) and title_value.strip():
        metadata_parts.append(f"title={_truncate_line(title_value)}")
    if isinstance(url_value, str) and url_value.strip():
        metadata_parts.append(f"url={_truncate_line(url_value)}")
    if isinstance(truncated_value, bool):
        metadata_parts.append(f"truncated={'yes' if truncated_value else 'no'}")
    if metadata_parts:
        lines.append(f"browser_snapshot page: {'; '.join(metadata_parts)}")
    snapshot_value = payload.get("snapshot")
    if not isinstance(snapshot_value, str) or not snapshot_value.strip():
        return _dedupe_preserve_order(lines)
    snapshot_lines = snapshot_value.splitlines()
    for start, end in _collect_interesting_windows(snapshot_lines):
        window_parts = [
            _normalize_snapshot_line(line)
            for line in snapshot_lines[start:end]
            if _is_contextual_snapshot_line(line)
        ]
        if not window_parts:
            continue
        lines.append(f"browser_snapshot fact: {' | '.join(window_parts)}")
    return _dedupe_preserve_order(lines)
