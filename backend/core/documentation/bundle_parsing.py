"""SoAI - Installed documentation bundle parsing [backend/core/documentation/bundle_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType

from core.errors.exceptions import ValidationError
from core.formatting.markdown_code_segments import split_fenced_segments

__all__ = (
    "DocumentationCorpus",
    "DocumentationPage",
    "DocumentationRecord",
    "parse_documentation_bundle",
)

_HEADING_PATTERN = r"^(#{1,6}) ([^\r\n]+)(?:\r?\n|$)"
_PAGE_PATTERN = r"^(.+?) \[page: ([a-z0-9][a-z0-9-]*)\]$"


@dataclass(frozen=True, slots=True)
class DocumentationRecord:
    identity: int
    page_id: str
    page_title: str
    section: str
    heading_path: tuple[str, ...]
    body: str
    start_offset: int
    end_offset: int


@dataclass(frozen=True, slots=True)
class DocumentationPage:
    page_id: str
    title: str
    section: str
    content: str
    records: tuple[DocumentationRecord, ...]


@dataclass(frozen=True, slots=True)
class DocumentationCorpus:
    source: str
    pages: tuple[DocumentationPage, ...]
    pages_by_id: MappingProxyType[str, DocumentationPage]
    records: tuple[DocumentationRecord, ...]


@dataclass(frozen=True, slots=True)
class _Heading:
    level: int
    text: str
    start: int
    end: int


def _headings(source: str) -> tuple[_Heading, ...]:
    headings: list[_Heading] = []
    offset = 0
    for is_code, segment in split_fenced_segments(source):
        if not is_code:
            for match in re.finditer(_HEADING_PATTERN, segment, re.MULTILINE):
                headings.append(
                    _Heading(
                        level=len(match.group(1)),
                        text=match.group(2).strip(),
                        start=offset + match.start(),
                        end=offset + match.end(),
                    )
                )
        offset += len(segment)
    return tuple(headings)


def _validate_fenced_segments(source: str) -> None:
    for is_code, segment in split_fenced_segments(source):
        if not is_code:
            continue
        lines = segment.splitlines()
        if len(lines) < 2:
            raise ValidationError("Documentation bundle contains an unterminated code fence")
        opening = lines[0].lstrip()
        fence_character = opening[0]
        minimum_length = len(opening) - len(opening.lstrip(fence_character))
        closing = lines[-1].strip()
        if (
            len(closing) < minimum_length
            or closing[0] != fence_character
            or closing.strip(fence_character)
        ):
            raise ValidationError("Documentation bundle contains an unterminated code fence")


def _content_start(source: str, heading_end: int) -> int:
    start = heading_end
    if source.startswith("\n", start):
        start += 1
    return start


def _build_records(
    *,
    page_id: str,
    page_title: str,
    section: str,
    content: str,
    identity_start: int,
) -> tuple[DocumentationRecord, ...]:
    fragment_headings = tuple(heading for heading in _headings(content) if heading.level >= 4)
    boundaries = (0,) + tuple(heading.start for heading in fragment_headings) + (len(content),)
    records: list[DocumentationRecord] = []
    ancestry: list[tuple[int, str]] = []
    suppress_level: int | None = None
    for index in range(len(boundaries) - 1):
        start = boundaries[index]
        end = boundaries[index + 1]
        heading = fragment_headings[index - 1] if index > 0 else None
        if heading is not None:
            while ancestry and ancestry[-1][0] >= heading.level:
                ancestry.pop()
            ancestry.append((heading.level, heading.text))
            if heading.text.casefold() == "related documentation":
                suppress_level = heading.level
            elif suppress_level is not None and heading.level <= suppress_level:
                suppress_level = None
        body = content[start:end].strip("\n")
        body_start = start + len(content[start:end]) - len(content[start:end].lstrip("\n"))
        if body and suppress_level is None:
            records.append(
                DocumentationRecord(
                    identity=identity_start + len(records),
                    page_id=page_id,
                    page_title=page_title,
                    section=section,
                    heading_path=tuple(value for _level, value in ancestry),
                    body=body,
                    start_offset=body_start,
                    end_offset=body_start + len(body),
                )
            )
    return tuple(records)


def parse_documentation_bundle(source: str) -> DocumentationCorpus:
    if not source:
        raise ValidationError("Documentation bundle is empty")
    _validate_fenced_segments(source)
    headings = _headings(source)
    if not headings or headings[0].level != 1 or headings[0].text != "SoAI Documentation":
        raise ValidationError("Documentation bundle root heading is invalid")
    page_markers: list[tuple[_Heading, str, str, str]] = []
    section: str | None = None
    section_has_page = False
    seen_ids: set[str] = set()
    for heading in headings[1:]:
        if heading.level == 1:
            raise ValidationError("Documentation bundle contains an unexpected root heading")
        if heading.level == 2:
            if section is not None and not section_has_page:
                raise ValidationError(f"Documentation section contains no pages: {section}")
            section = heading.text
            section_has_page = False
            continue
        if heading.level != 3:
            if not section_has_page:
                raise ValidationError("Documentation fragment heading appears outside a page")
            continue
        match = re.fullmatch(_PAGE_PATTERN, heading.text)
        if match is None:
            raise ValidationError("Documentation page heading has no canonical page marker")
        if section is None:
            raise ValidationError("Documentation page appears outside a section")
        page_title, page_id = match.groups()
        if page_id in seen_ids:
            raise ValidationError(f"Duplicate documentation page ID: {page_id}")
        seen_ids.add(page_id)
        section_has_page = True
        page_markers.append((heading, page_title, page_id, section))
    if section is not None and not section_has_page:
        raise ValidationError(f"Documentation section contains no pages: {section}")
    if not page_markers:
        raise ValidationError("Documentation bundle contains no pages")
    pages: list[DocumentationPage] = []
    all_records: list[DocumentationRecord] = []
    for heading, title, page_id, page_section in page_markers:
        boundary = next(
            (
                candidate.start
                for candidate in headings
                if candidate.start > heading.start and candidate.level <= 3
            ),
            len(source),
        )
        content = source[_content_start(source, heading.end) : boundary].rstrip("\n")
        records = _build_records(
            page_id=page_id,
            page_title=title,
            section=page_section,
            content=content,
            identity_start=len(all_records),
        )
        all_records.extend(records)
        pages.append(
            DocumentationPage(
                page_id=page_id,
                title=title,
                section=page_section,
                content=content,
                records=records,
            )
        )
    pages_by_id = MappingProxyType({page.page_id: page for page in pages})
    return DocumentationCorpus(
        source=source,
        pages=tuple(pages),
        pages_by_id=pages_by_id,
        records=tuple(all_records),
    )
