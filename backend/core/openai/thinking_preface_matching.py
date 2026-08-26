"""SoAI - Thinking preface committed text matching [backend/core/openai/thinking_preface_matching.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.openai.thinking_preface_display import resolve_preface_match_text

__all__ = ("resolve_committed_preface_prefix_end_index",)


def _resolve_normalized_prefix_end_index(text: str, prefix: str) -> int | None:
    text_index = 0
    prefix_index = 0
    while prefix_index < len(prefix):
        prefix_character = prefix[prefix_index]
        if prefix_character.isspace():
            if text_index >= len(text) or not text[text_index].isspace():
                return None
            while text_index < len(text) and text[text_index].isspace():
                text_index += 1
            while prefix_index < len(prefix) and prefix[prefix_index].isspace():
                prefix_index += 1
            continue
        if text_index < len(text) and text[text_index].isspace() and prefix_index > 0:
            whitespace_start = text_index
            while text_index < len(text) and text[text_index].isspace():
                text_index += 1
            if (
                "\n" in text[whitespace_start:text_index]
                and prefix_character.isalnum()
                and prefix[prefix_index - 1] == "."
            ):
                continue
            text_index = whitespace_start
        if text_index >= len(text) or text[text_index] != prefix_character:
            return None
        text_index += 1
        prefix_index += 1
    return text_index


def resolve_committed_preface_prefix_end_index(
    text: str,
    prefix: str,
) -> int | None:
    committed_match_text = resolve_preface_match_text(prefix)
    if not committed_match_text:
        return None
    prefix_end_index = _resolve_normalized_prefix_end_index(text, committed_match_text)
    if prefix_end_index is not None:
        return prefix_end_index
    if not prefix.endswith(".") or prefix.endswith("..."):
        return None
    fallback_match_text = resolve_preface_match_text(prefix[:-1].rstrip())
    if not fallback_match_text:
        return None
    fallback_end_index = _resolve_normalized_prefix_end_index(text, fallback_match_text)
    if fallback_end_index is None:
        return None
    if fallback_end_index < len(text) and not text[fallback_end_index].isspace():
        return None
    return fallback_end_index
