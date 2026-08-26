"""SoAI - Thinking preface extraction and render-mode heuristics [backend/core/openai/thinking_preface.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.openai.thinking_preface_boundaries import (
    resolve_incomplete_thinking_preface_end_index,
    resolve_limited_thinking_preface_bounds,
    resolve_thinking_preface_bounds,
)
from core.openai.thinking_preface_display import (
    is_inline_safe_thinking_preface,
    is_truncated_preface_display,
    normalize_thinking_preface_display_text,
    normalize_thinking_preface_sentence,
    resolve_preface_body_display_text,
    resolve_short_preface_only_text,
    truncate_inline_thinking_preface,
)
from core.openai.thinking_preface_matching import (
    resolve_committed_preface_prefix_end_index,
)

__all__ = (
    "ThinkingPrefaceResolution",
    "resolve_committed_thinking_preface_rendering",
    "resolve_thinking_preface_rendering",
    "split_thinking_preface_and_body",
)


@dataclass(frozen=True, slots=True)
class ThinkingPrefaceResolution:
    render_mode: Literal["preface_only", "preface_and_thinking", "thinking_only"]
    text: str
    preface_text: str | None
    preface_complete: bool


@dataclass(frozen=True, slots=True)
class _ThinkingPrefaceParts:
    preface_text: str
    body_text: str
    preface_complete: bool


def _resolve_short_preface_only_rendering(
    text: str,
    *,
    preface_complete: bool,
) -> ThinkingPrefaceResolution | None:
    display_text = resolve_short_preface_only_text(text)
    if display_text is None:
        return None
    return ThinkingPrefaceResolution(
        render_mode="preface_only",
        text=display_text,
        preface_text=display_text,
        preface_complete=preface_complete,
    )


def _resolve_limited_preface_parts(text: str) -> _ThinkingPrefaceParts | None:
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return None
    bounds = resolve_limited_thinking_preface_bounds(normalized, sentence_limit=2)
    if bounds is None:
        return None
    preface_end_index, body_start_index, preface_complete = bounds
    preface_text = normalize_thinking_preface_sentence(normalized[:preface_end_index])
    if not preface_text:
        return None
    return _ThinkingPrefaceParts(
        preface_text=preface_text,
        body_text=normalized[body_start_index:].lstrip(),
        preface_complete=preface_complete,
    )


def _split_thinking_preface(text: str) -> _ThinkingPrefaceParts | None:
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return None
    bounds = resolve_thinking_preface_bounds(normalized)
    if bounds is None:
        end_index = resolve_incomplete_thinking_preface_end_index(normalized)
        body_start_index = end_index
        preface_complete = False
    else:
        end_index, body_start_index = bounds
        preface_complete = True
    preface_end_index = max(0, min(len(normalized), end_index))
    bounded_preface = normalized[:preface_end_index]
    preface_text = normalize_thinking_preface_sentence(bounded_preface)
    if not preface_text:
        return None
    resolved_body_start_index = max(0, min(len(normalized), body_start_index))
    body_text = normalized[resolved_body_start_index:].lstrip()
    return _ThinkingPrefaceParts(
        preface_text=preface_text,
        body_text=body_text,
        preface_complete=preface_complete,
    )


def split_thinking_preface_and_body(text: str) -> tuple[str, str] | None:
    parts = _split_thinking_preface(text)
    if parts is None:
        return None
    return parts.preface_text, parts.body_text


def resolve_thinking_preface_rendering(
    text: str,
    *,
    require_complete_preface: bool = False,
) -> ThinkingPrefaceResolution | None:
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return None
    if require_complete_preface:
        parts = _resolve_limited_preface_parts(normalized)
        if parts is None:
            return None
        source_preface_text = parts.preface_text
        preface_text = truncate_inline_thinking_preface(source_preface_text)
        preface_truncated = is_truncated_preface_display(
            source_preface_text,
            preface_text,
        )
        body_text = resolve_preface_body_display_text(
            source_preface_text,
            preface_text,
            parts.body_text,
            is_truncated_preface=preface_truncated,
        )
        if body_text and (parts.preface_complete or preface_truncated):
            return ThinkingPrefaceResolution(
                render_mode="preface_and_thinking",
                text=body_text,
                preface_text=preface_text,
                preface_complete=True,
            )
        return ThinkingPrefaceResolution(
            render_mode="preface_only",
            text=body_text or preface_text,
            preface_text=preface_text,
            preface_complete=False,
        )
    parts = _resolve_limited_preface_parts(normalized)
    if parts is None:
        return None
    short_resolution = _resolve_short_preface_only_rendering(
        parts.preface_text,
        preface_complete=parts.preface_complete,
    )
    if short_resolution is not None and not parts.body_text:
        return short_resolution
    if not parts.preface_complete:
        if is_inline_safe_thinking_preface(parts.preface_text):
            preface_text = truncate_inline_thinking_preface(parts.preface_text)
            preface_truncated = is_truncated_preface_display(
                parts.preface_text,
                preface_text,
            )
            body_text = resolve_preface_body_display_text(
                parts.preface_text,
                preface_text,
                parts.body_text,
                is_truncated_preface=preface_truncated,
            )
            if body_text and preface_truncated:
                return ThinkingPrefaceResolution(
                    render_mode="preface_and_thinking",
                    text=body_text,
                    preface_text=preface_text,
                    preface_complete=True,
                )
            return ThinkingPrefaceResolution(
                render_mode="preface_only",
                text=body_text or preface_text,
                preface_text=preface_text,
                preface_complete=False,
            )
        return ThinkingPrefaceResolution(
            render_mode="thinking_only",
            text=normalized,
            preface_text=None,
            preface_complete=False,
        )
    body_text = parts.body_text
    if not is_inline_safe_thinking_preface(parts.preface_text):
        return ThinkingPrefaceResolution(
            render_mode="thinking_only",
            text=normalized,
            preface_text=None,
            preface_complete=False,
        )
    preface_text = truncate_inline_thinking_preface(parts.preface_text)
    display_body_text = resolve_preface_body_display_text(
        parts.preface_text,
        preface_text,
        body_text,
        is_truncated_preface=is_truncated_preface_display(
            parts.preface_text,
            preface_text,
        ),
    )
    if display_body_text:
        return ThinkingPrefaceResolution(
            render_mode="preface_and_thinking",
            text=display_body_text,
            preface_text=preface_text,
            preface_complete=True,
        )
    return ThinkingPrefaceResolution(
        render_mode="preface_only",
        text=preface_text,
        preface_text=preface_text,
        preface_complete=True,
    )


def resolve_committed_thinking_preface_rendering(
    text: str,
    committed_preface_text: str,
) -> ThinkingPrefaceResolution | None:
    normalized = text.replace("\r\n", "\n").strip()
    committed_preface = normalize_thinking_preface_display_text(committed_preface_text)
    if not normalized or not committed_preface:
        return None
    prefix_end_index = resolve_committed_preface_prefix_end_index(
        normalized,
        committed_preface,
    )
    if prefix_end_index is None:
        return None
    body_text = normalized[prefix_end_index:].lstrip()
    if body_text:
        return ThinkingPrefaceResolution(
            render_mode="preface_and_thinking",
            text=resolve_preface_body_display_text(
                normalize_thinking_preface_sentence(normalized),
                committed_preface,
                body_text,
                is_truncated_preface=is_truncated_preface_display(
                    normalize_thinking_preface_sentence(normalized),
                    committed_preface,
                ),
            ),
            preface_text=committed_preface,
            preface_complete=True,
        )
    return ThinkingPrefaceResolution(
        render_mode="preface_only",
        text=committed_preface,
        preface_text=committed_preface,
        preface_complete=True,
    )
