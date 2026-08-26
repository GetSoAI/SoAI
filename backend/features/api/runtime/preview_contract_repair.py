"""SoAI - Deterministic preview-contract prose repair [backend/features/api/runtime/preview_contract_repair.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass

from core.formatting.markdown_code_segments import (
    split_fenced_segments,
    split_inline_code_segments,
)
from core.preview_contract.preview_contract import build_preview_reference

__all__ = (
    "PreviewContractRepairResult",
    "attempt_preview_contract_repair",
)

_MARKDOWN_IMAGE_PATTERN_TEXT = r"!\[([^\]]*)\]\((https://[^)\s]+)\)"
_MARKDOWN_LINK_PATTERN_TEXT = r"\[([^\]]+)\]\((https://[^)\s]+)\)"
_HTML_IMAGE_PATTERN_TEXT = r"<img\b[^>]*>"
_HTML_SRC_PATTERN_TEXT = r"""src\s*=\s*(['"])(https://[^'"]+)\1"""
_HTML_ALT_PATTERN_TEXT = r"""alt\s*=\s*(['"])([^'"]*)\1"""
_HTML_TITLE_PATTERN_TEXT = r"""title\s*=\s*(['"])([^'"]*)\1"""
_RAW_REMOTE_URL_PATTERN_TEXT = r"""(?<!\[\[preview:remote_url:)([<"']?)https://[^\s<>\]"']+"""
_CANONICAL_PREVIEW_REFERENCE_PATTERN_TEXT = (
    r"^\s*\[\[preview:(absolute_path|virtual_path|remote_url):([^\]|]+)(?:\|([^\]]+))?\]\]\s*$"
)


@dataclass(frozen=True, slots=True)
class PreviewContractRepairResult:
    text: str
    changed: bool


def _unwrap_inline_code_preview_reference(code_span: str) -> str | None:
    normalized = str(code_span or "")
    if not normalized.startswith("`"):
        return None
    index = 0
    while index < len(normalized) and normalized[index] == "`":
        index += 1
    if index <= 0:
        return None
    delimiter = normalized[:index]
    if len(normalized) < (len(delimiter) * 2) or not normalized.endswith(delimiter):
        return None
    inner = normalized[len(delimiter) : -len(delimiter)]
    match = re.match(_CANONICAL_PREVIEW_REFERENCE_PATTERN_TEXT, inner)
    if match is None:
        return None
    reference_type = str(match.group(1) or "").strip()
    target = str(match.group(2) or "").strip()
    label = str(match.group(3) or "").strip()
    if not reference_type or not target:
        return None
    return build_preview_reference(
        reference_type=reference_type,
        target=target,
        label=label or None,
    )


def _trim_trailing_punctuation(url: str) -> tuple[str, str]:
    resolved_url = url
    while True:
        if resolved_url and resolved_url[-1] in ">\"'.,;!?:":
            resolved_url = resolved_url[:-1]
            continue
        if resolved_url.endswith(")") and resolved_url.count("(") < resolved_url.count(")"):
            resolved_url = resolved_url[:-1]
            continue
        break
    return (resolved_url, url[len(resolved_url) :])


def _build_remote_reference(url: str, label: str | None = None) -> str:
    normalized_label = str(label or "").strip()
    return build_preview_reference(
        reference_type="remote_url",
        target=url,
        label=normalized_label or None,
    )


def _replace_html_image(match: re.Match[str]) -> str:
    raw_tag = match.group(0)
    src_match = re.search(_HTML_SRC_PATTERN_TEXT, raw_tag, flags=re.IGNORECASE)
    if src_match is None:
        return raw_tag
    url = str(src_match.group(2) or "").strip()
    if not url:
        return raw_tag
    alt_match = re.search(_HTML_ALT_PATTERN_TEXT, raw_tag, flags=re.IGNORECASE)
    title_match = re.search(_HTML_TITLE_PATTERN_TEXT, raw_tag, flags=re.IGNORECASE)
    label = str((alt_match.group(2) if alt_match is not None else "") or "").strip()
    if not label:
        label = str((title_match.group(2) if title_match is not None else "") or "").strip()
    return _build_remote_reference(url, label or None)


def _replace_markdown_image(match: re.Match[str]) -> str:
    alt_text = str(match.group(1) or "").strip()
    url = str(match.group(2) or "").strip()
    return _build_remote_reference(url, alt_text or None)


def _replace_markdown_link(match: re.Match[str]) -> str:
    label = str(match.group(1) or "").strip()
    url = str(match.group(2) or "").strip()
    return _build_remote_reference(url, label or None)


def _replace_raw_remote_url(match: re.Match[str]) -> str:
    raw_token = str(match.group(0) or "")
    leading_delimiter = str(match.group(1) or "")
    raw_url = (
        raw_token[len(leading_delimiter) :].strip() if leading_delimiter else raw_token.strip()
    )
    resolved_url, suffix = _trim_trailing_punctuation(raw_url)
    if not resolved_url:
        return raw_token
    preserve_leading_delimiter = leading_delimiter
    if leading_delimiter == "<" and suffix.startswith(">"):
        suffix = suffix[1:]
        preserve_leading_delimiter = ""
    return f"{preserve_leading_delimiter}{_build_remote_reference(resolved_url)}{suffix}"


def _repair_prose_segment(text: str) -> str:
    repaired = re.sub(
        _HTML_IMAGE_PATTERN_TEXT,
        _replace_html_image,
        text,
        flags=re.IGNORECASE,
    )
    repaired = re.sub(
        _MARKDOWN_IMAGE_PATTERN_TEXT,
        _replace_markdown_image,
        repaired,
    )
    repaired = re.sub(
        _MARKDOWN_LINK_PATTERN_TEXT,
        _replace_markdown_link,
        repaired,
    )
    return re.sub(
        _RAW_REMOTE_URL_PATTERN_TEXT,
        _replace_raw_remote_url,
        repaired,
    )


def attempt_preview_contract_repair(text: str) -> PreviewContractRepairResult:
    normalized_text = str(text or "")
    if not normalized_text:
        return PreviewContractRepairResult(text="", changed=False)
    repaired_segments: list[str] = []
    for protected_fence, fenced_segment in split_fenced_segments(normalized_text):
        if protected_fence:
            repaired_segments.append(fenced_segment)
            continue
        for protected_inline_code, prose_segment in split_inline_code_segments(fenced_segment):
            if protected_inline_code:
                unwrapped = _unwrap_inline_code_preview_reference(prose_segment)
                repaired_segments.append(unwrapped if unwrapped is not None else prose_segment)
                continue
            repaired_segments.append(_repair_prose_segment(prose_segment))
    repaired_text = "".join(repaired_segments)
    return PreviewContractRepairResult(
        text=repaired_text,
        changed=repaired_text != normalized_text,
    )
