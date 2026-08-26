"""SoAI - Canonical WebUI preview contract helpers [backend/core/preview_contract/preview_contract.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache

from core.preview_contract.preview_contract_renderable_text import (
    coerce_preview_contract_text_without_fenced_code_blocks,
    coerce_renderable_preview_contract_text,
)

__all__ = (
    "PREVIEW_CONTRACT_VIOLATION_CODE",
    "PREVIEW_CONTRACT_VIOLATION_PUBLIC_MESSAGE",
    "PreviewContractSyntaxAnalysis",
    "PreviewReference",
    "PreviewReferenceType",
    "allowed_preview_reference_types",
    "analyze_preview_contract_syntax",
    "build_preview_contract_requirement_system_message",
    "build_preview_reference",
    "is_preview_contract_compliant",
    "parse_preview_references",
    "parse_renderable_preview_references",
    "render_preview_references_as_plain_text",
)

PreviewReferenceType = str

_ALLOWED_PREVIEW_REFERENCE_TYPES: tuple[PreviewReferenceType, ...] = (
    "absolute_path",
    "virtual_path",
    "remote_url",
)
_PREVIEW_REFERENCE_PATTERN_SOURCE = (
    r"\[\[preview:(absolute_path|virtual_path|remote_url):([^\]|]+)(?:\|([^\]]+))?\]\]"
)
_NONCANONICAL_INLINE_REFERENCE_PATTERN_SOURCE = r"\[\[[^\]]+\]\]"
_RAW_REMOTE_URL_PATTERN_SOURCE = r"https?://\S+"
_MARKDOWN_IMAGE_PATTERN_SOURCE = r"!\[[^\]]*\]\([^)]+\)"
_HTML_IMAGE_TAG_PATTERN_SOURCE = r"<img\b[^>]*>"
_PREVIEW_CONTRACT_PREFIX = "<soai_preview_contract>"
PREVIEW_CONTRACT_VIOLATION_CODE = "preview_contract_violation"
PREVIEW_CONTRACT_VIOLATION_PUBLIC_MESSAGE = "SoAI could not generate a previewable answer for this turn. Retry or ask for direct text instead."


@dataclass(frozen=True, slots=True)
class PreviewReference:
    type: PreviewReferenceType
    target: str
    label: str | None
    raw: str


@dataclass(frozen=True, slots=True)
class PreviewContractSyntaxAnalysis:
    compliant: bool
    references: tuple[PreviewReference, ...]
    reason_code: str | None


def allowed_preview_reference_types() -> tuple[PreviewReferenceType, ...]:
    return _ALLOWED_PREVIEW_REFERENCE_TYPES


@cache
def _preview_reference_pattern() -> re.Pattern[str]:
    return re.compile(_PREVIEW_REFERENCE_PATTERN_SOURCE)


@cache
def _noncanonical_inline_reference_pattern() -> re.Pattern[str]:
    return re.compile(_NONCANONICAL_INLINE_REFERENCE_PATTERN_SOURCE)


@cache
def _raw_remote_url_pattern() -> re.Pattern[str]:
    return re.compile(_RAW_REMOTE_URL_PATTERN_SOURCE)


@cache
def _markdown_image_pattern() -> re.Pattern[str]:
    return re.compile(_MARKDOWN_IMAGE_PATTERN_SOURCE)


@cache
def _html_image_tag_pattern() -> re.Pattern[str]:
    return re.compile(_HTML_IMAGE_TAG_PATTERN_SOURCE, re.IGNORECASE)


def parse_preview_references(text: str) -> tuple[PreviewReference, ...]:
    if not isinstance(text, str) or not text:
        return ()
    references: list[PreviewReference] = []
    pattern = _preview_reference_pattern()
    for match in pattern.finditer(text):
        type_text = str(match.group(1) or "").strip()
        target = str(match.group(2) or "").strip()
        label_text = str(match.group(3) or "").strip()
        if type_text not in _ALLOWED_PREVIEW_REFERENCE_TYPES:
            continue
        if not target:
            continue
        references.append(
            PreviewReference(
                type=type_text,
                target=target,
                label=label_text or None,
                raw=str(match.group(0) or ""),
            ),
        )
    return tuple(references)


def render_preview_references_as_plain_text(text: str) -> str:
    rendered_text = text
    for reference in parse_preview_references(text):
        replacement = reference.target
        if reference.label is not None:
            replacement = f"{reference.label} ({reference.target})"
        rendered_text = rendered_text.replace(reference.raw, replacement)
    return rendered_text


def _contains_preview_reference_inside_html_tag(
    text: str,
    references: tuple[PreviewReference, ...],
) -> bool:
    search_start = 0
    for reference in references:
        raw_reference = reference.raw
        match_index = text.find(raw_reference, search_start)
        if match_index < 0:
            match_index = text.find(raw_reference)
            if match_index < 0:
                continue
        tag_open_index = text.rfind("<", 0, match_index)
        if tag_open_index < 0:
            search_start = match_index + len(raw_reference)
            continue
        if tag_open_index + 1 >= len(text):
            search_start = match_index + len(raw_reference)
            continue
        tag_indicator = text[tag_open_index + 1]
        if not (tag_indicator.isalpha() or tag_indicator in ("/", "!", "?")):
            search_start = match_index + len(raw_reference)
            continue
        tag_close_index = text.rfind(">", 0, match_index)
        if tag_close_index < tag_open_index:
            return True
        search_start = match_index + len(raw_reference)
    return False


def parse_renderable_preview_references(text: str) -> tuple[PreviewReference, ...]:
    renderable = coerce_renderable_preview_contract_text(text)
    if not renderable:
        return ()
    return parse_preview_references(renderable)


def build_preview_reference(
    *,
    reference_type: PreviewReferenceType,
    target: str,
    label: str | None = None,
) -> str:
    normalized_target = str(target or "").strip()
    if reference_type not in _ALLOWED_PREVIEW_REFERENCE_TYPES:
        raise ValueError("Unsupported preview reference type.")
    if not normalized_target:
        raise ValueError("Preview reference target must be non-empty.")
    normalized_label = str(label or "").strip()
    if normalized_label:
        return f"[[preview:{reference_type}:{normalized_target}|{normalized_label}]]"
    return f"[[preview:{reference_type}:{normalized_target}]]"


def analyze_preview_contract_syntax(assistant_text: str) -> PreviewContractSyntaxAnalysis:
    text_without_fences = coerce_preview_contract_text_without_fenced_code_blocks(assistant_text)
    renderable_text = coerce_renderable_preview_contract_text(assistant_text)
    references = parse_preview_references(renderable_text)
    if not references:
        return PreviewContractSyntaxAnalysis(
            compliant=False,
            references=(),
            reason_code="missing_preview_reference",
        )
    if _contains_preview_reference_inside_html_tag(renderable_text, references):
        return PreviewContractSyntaxAnalysis(
            compliant=False,
            references=references,
            reason_code="noncanonical_reference_syntax",
        )
    text_without_preview_tokens = text_without_fences
    for reference in references:
        text_without_preview_tokens = text_without_preview_tokens.replace(reference.raw, " ")
    if _noncanonical_inline_reference_pattern().search(text_without_preview_tokens):
        return PreviewContractSyntaxAnalysis(
            compliant=False,
            references=references,
            reason_code="noncanonical_reference_syntax",
        )
    if _markdown_image_pattern().search(text_without_preview_tokens):
        return PreviewContractSyntaxAnalysis(
            compliant=False,
            references=references,
            reason_code="noncanonical_reference_syntax",
        )
    if _html_image_tag_pattern().search(text_without_preview_tokens):
        return PreviewContractSyntaxAnalysis(
            compliant=False,
            references=references,
            reason_code="noncanonical_reference_syntax",
        )
    if _raw_remote_url_pattern().search(text_without_preview_tokens) is not None:
        return PreviewContractSyntaxAnalysis(
            compliant=False,
            references=references,
            reason_code="noncanonical_reference_syntax",
        )
    return PreviewContractSyntaxAnalysis(
        compliant=True,
        references=references,
        reason_code=None,
    )


def is_preview_contract_compliant(assistant_text: str) -> bool:
    return analyze_preview_contract_syntax(assistant_text).compliant


def build_preview_contract_requirement_system_message() -> str:
    lines = [
        _PREVIEW_CONTRACT_PREFIX,
        "This turn requires the SoAI WebUI preview contract.",
        "If you present inspectable media or files, emit canonical preview references only in the visible assistant response body.",
        "Each reference has exactly one of two shapes.",
        "Without a label: [[preview:<type>:<target>]]",
        "With a label:    [[preview:<type>:<target>|<label>]]",
        "Concrete examples per type, without a label:",
        "- [[preview:absolute_path:/srv/files/report.pdf]]",
        "- [[preview:virtual_path:/folder/file.txt]]",
        "- [[preview:remote_url:https://example.com/page]]",
        "Concrete examples per type, with a label:",
        "- [[preview:absolute_path:/srv/files/report.pdf|Quarterly report]]",
        "- [[preview:virtual_path:/folder/file.txt|Notes]]",
        "- [[preview:remote_url:https://example.com/page|Example page]]",
        "Structural rule: every reference ends with the literal two characters ]] as its final two characters. The | separator, when used, sits inside the brackets between the target and the label. Never write ] between the target and the |, and never end a reference with a single ].",
        "Wrong: [[preview:remote_url:https://example.com/page]|Example page]",
        "Right: [[preview:remote_url:https://example.com/page|Example page]]",
        "Use absolute_path only for real absolute OS filesystem paths on the SoAI host, such as /srv/files/report.pdf.",
        "Use virtual_path only for File Explorer virtual paths rooted at /, such as /folder/file.txt.",
        "Do not put an OS filesystem path into virtual_path. If the File Explorer root is /srv/files, the OS path /srv/files/reports/a.md maps to virtual_path /reports/a.md.",
        "Never use a plain URL for links or media you intend the user to open or inspect in the SoAI WebUI.",
        "URLs are allowed only inside fenced code blocks when you are writing code examples. Do not put plain URLs in prose or inside backticks.",
        "Do not rely on plain URLs, Markdown images, or HTML image tags as preview output.",
        "Do not put preview references in tool calls, tool arguments, tool results, notifications, or any other side channel.",
        "Do not place preview references inside fenced code blocks or backticks. Emit them only in normal assistant prose at the end of the final assistant response to render.",
        "Do not claim content is shown, displayed, previewed, or visible unless your response includes valid canonical preview references.",
        "</soai_preview_contract>",
    ]
    return "\n".join(lines)
