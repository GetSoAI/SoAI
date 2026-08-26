"""SoAI - Ordered document raster extraction [backend/files/parsers/document_ocr_rasters.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import posixpath
import re
import threading
import time
import zipfile
from collections import deque
from functools import partial
from xml.etree.ElementTree import Element

import pypdfium2
from defusedxml import ElementTree

from core.archives.zip_plan import (
    ValidatedZipMember,
    ZipPlanPolicy,
    build_validated_zip_plan,
)
from core.archives.zip_plan_extraction import extract_validated_zip_members
from core.errors.exceptions import StateError
from core.files.image_candidates import is_supported_image_candidate
from files.parsers.document_ocr_types import RasterCandidate
from files.parsers.document_text_slicing import is_extraction_readable

__all__ = ("extract_ordered_document_rasters", "supports_document_raster_extraction")

_WORD_ARCHIVE_EXTENSIONS = frozenset(("docx", "docm", "dotx", "dotm"))
_PRESENTATION_ARCHIVE_EXTENSIONS = frozenset(("pptx", "pptm", "potx", "potm", "ppsx", "ppsm"))
_SPREADSHEET_ARCHIVE_EXTENSIONS = frozenset(("xlsx", "xlsm", "xltx", "xltm"))
_OPEN_DOCUMENT_ARCHIVE_EXTENSIONS = frozenset(("odt", "ods", "odp"))
_SUPPORTED_ARCHIVE_EXTENSIONS = frozenset(
    (
        *_WORD_ARCHIVE_EXTENSIONS,
        *_PRESENTATION_ARCHIVE_EXTENSIONS,
        *_SPREADSHEET_ARCHIVE_EXTENSIONS,
        *_OPEN_DOCUMENT_ARCHIVE_EXTENSIONS,
        "epub",
    )
)
_PDF_RENDER_SCALE = 2.0
_UNIT_NUMBER_PATTERN = r"(?:slide|sheet)(\d+)\.xml$"


def supports_document_raster_extraction(extension: str) -> bool:
    return extension == "pdf" or extension in _SUPPORTED_ARCHIVE_EXTENSIONS


def extract_ordered_document_rasters(
    source_path: str,
    extension: str,
    destination: str,
    deadline: float,
    cancellation_event: threading.Event | None,
) -> tuple[tuple[RasterCandidate, ...], int | None]:
    if extension == "pdf":
        return _render_raster_only_pdf_pages(
            source_path,
            destination,
            deadline,
            cancellation_event,
        )
    root_member = _resolve_archive_root_member(extension)
    if root_member is None:
        return (), None
    return (
        _extract_ordered_archive_images(
            source_path,
            root_member,
            destination,
            deadline,
            cancellation_event,
        ),
        None,
    )


def _resolve_archive_root_member(extension: str) -> str | None:
    if extension in _WORD_ARCHIVE_EXTENSIONS:
        return "word/document.xml"
    if extension in _PRESENTATION_ARCHIVE_EXTENSIONS:
        return "ppt/presentation.xml"
    if extension in _SPREADSHEET_ARCHIVE_EXTENSIONS:
        return "xl/workbook.xml"
    if extension in _OPEN_DOCUMENT_ARCHIVE_EXTENSIONS:
        return "content.xml"
    if extension == "epub":
        return "META-INF/container.xml"
    return None


def _render_raster_only_pdf_pages(
    source_path: str,
    destination: str,
    deadline: float,
    cancellation_event: threading.Event | None,
) -> tuple[tuple[RasterCandidate, ...], int]:
    pdf = pypdfium2.PdfDocument(source_path)
    candidates: list[RasterCandidate] = []
    try:
        page_count = len(pdf)
        for page_index in range(page_count):
            _raise_if_stopped(deadline, cancellation_event)
            page = pdf.get_page(page_index)
            try:
                text_page = page.get_textpage()
                try:
                    native_text = text_page.get_text_range()
                finally:
                    text_page.close()
                if is_extraction_readable(native_text):
                    continue
                bitmap = page.render(scale=_PDF_RENDER_SCALE)
                try:
                    image = bitmap.to_pil()
                finally:
                    bitmap.close()
                image_path = os.path.join(destination, f"pdf-page-{page_index + 1}.png")
                try:
                    image.save(image_path, format="PNG")
                finally:
                    image.close()
                candidates.append(RasterCandidate(label=f"Page {page_index + 1}", path=image_path))
            finally:
                page.close()
        return tuple(candidates), page_count
    finally:
        pdf.close()


def _extract_ordered_archive_images(
    source_path: str,
    root_member: str,
    destination: str,
    deadline: float,
    cancellation_event: threading.Event | None,
) -> tuple[RasterCandidate, ...]:
    try:
        with zipfile.ZipFile(source_path) as archive:
            plan = build_validated_zip_plan(
                archive,
                policy=ZipPlanPolicy(
                    reject_backslashes=True,
                    reject_colons=True,
                    reject_empty_segments=True,
                    reject_case_collisions=True,
                    reject_unicode_collisions=True,
                ),
            )
            member_map = {member.archive_path: member for member in plan.members}
            ordered_images = _walk_ordered_references(
                archive,
                member_map,
                root_member,
                deadline,
                cancellation_event,
            )
            selected_members = tuple(member_map[path] for _source, path in ordered_images)
            extract_validated_zip_members(
                archive,
                selected_members,
                destination,
                progress_check=partial(_raise_if_stopped, deadline, cancellation_event),
            )
    except zipfile.BadZipFile as exception:
        raise StateError("Document container is not a valid ZIP archive.") from exception
    candidates: list[RasterCandidate] = []
    for index, (source_member, image_member) in enumerate(ordered_images, start=1):
        candidates.append(
            RasterCandidate(
                label=_candidate_label(source_member, index),
                path=os.path.join(destination, member_map[image_member].destination_path),
            ),
        )
    return tuple(candidates)


def _walk_ordered_references(
    archive: zipfile.ZipFile,
    member_map: dict[str, ValidatedZipMember],
    root_member: str,
    deadline: float,
    cancellation_event: threading.Event | None,
) -> tuple[tuple[str, str], ...]:
    queue: deque[str] = deque((root_member,))
    visited: set[str] = set()
    images: list[tuple[str, str]] = []
    seen_images: set[str] = set()
    while queue:
        _raise_if_stopped(deadline, cancellation_event)
        source_member = queue.popleft()
        if source_member in visited or source_member not in member_map:
            continue
        visited.add(source_member)
        root = ElementTree.fromstring(archive.read(source_member))
        relationships = _read_relationships(archive, member_map, source_member)
        for reference in _ordered_attribute_references(
            root,
            skip_identifier_targets=source_member.casefold().endswith(".opf"),
        ):
            target = relationships.get(reference, reference)
            resolved = _resolve_archive_target(source_member, target)
            if resolved not in member_map:
                continue
            if is_supported_image_candidate(path=resolved, content_type=None):
                if resolved not in seen_images:
                    images.append((source_member, resolved))
                    seen_images.add(resolved)
            elif resolved.lower().endswith((".xml", ".xhtml", ".html", ".htm", ".opf")):
                queue.append(resolved)
    return tuple(images)


def _read_relationships(
    archive: zipfile.ZipFile,
    member_map: dict[str, ValidatedZipMember],
    source_member: str,
) -> dict[str, str]:
    source_directory = posixpath.dirname(source_member)
    relationship_member = posixpath.join(
        source_directory,
        "_rels",
        f"{posixpath.basename(source_member)}.rels",
    )
    if relationship_member not in member_map:
        return {}
    root = ElementTree.fromstring(archive.read(relationship_member))
    relationships: dict[str, str] = {}
    for element in root.iter():
        attributes = element.attrib
        relationship_id = attributes.get("Id", "")
        target = attributes.get("Target", "")
        target_mode = attributes.get("TargetMode", "")
        if relationship_id and target and target_mode.casefold() != "external":
            relationships[relationship_id] = target
    return relationships


def _ordered_attribute_references(
    root: Element,
    *,
    skip_identifier_targets: bool,
) -> tuple[str, ...]:
    local_references: dict[str, str] = {}
    for element in root.iter():
        attributes = {
            name.rsplit("}", 1)[-1].casefold(): value.strip()
            for name, value in element.attrib.items()
            if value.strip()
        }
        identifier = attributes.get("id", "")
        target = attributes.get("href", "")
        full_path = attributes.get("full-path", "")
        if not target and full_path:
            target = f"/{full_path.lstrip('/')}"
        if identifier and target:
            local_references[identifier] = target
    references: list[str] = []
    declaration_targets = set(local_references.values())
    for element in root.iter():
        for attribute_name, value in element.attrib.items():
            local_name = attribute_name.rsplit("}", 1)[-1].casefold()
            stripped = value.strip()
            if not stripped:
                continue
            if (
                skip_identifier_targets
                and local_name in {"href", "full-path"}
                and stripped in declaration_targets
            ):
                continue
            if local_name in {"embed", "link", "href", "full-path", "src"} or local_name == "idref":
                reference = f"/{stripped.lstrip('/')}" if local_name == "full-path" else stripped
                references.append(local_references.get(stripped, reference))
            elif local_name == "id" and "relationships" in attribute_name.casefold():
                references.append(stripped)
    return tuple(references)


def _resolve_archive_target(source_member: str, target: str) -> str:
    normalized_target = target.replace("\\", "/").split("#", 1)[0]
    if normalized_target.startswith("/"):
        normalized_target = normalized_target.lstrip("/")
    else:
        normalized_target = posixpath.join(posixpath.dirname(source_member), normalized_target)
    resolved = posixpath.normpath(normalized_target)
    if resolved == ".." or resolved.startswith("../"):
        return ""
    return resolved


def _candidate_label(source_member: str, fallback_index: int) -> str:
    match = re.search(_UNIT_NUMBER_PATTERN, source_member, re.IGNORECASE)
    if match is not None:
        unit = "Slide" if "slide" in source_member.casefold() else "Sheet"
        return f"{unit} {match.group(1)} image"
    return f"Document image {fallback_index}"


def _raise_if_stopped(
    deadline: float,
    cancellation_event: threading.Event | None,
) -> None:
    if cancellation_event is not None and cancellation_event.is_set():
        raise asyncio.CancelledError
    if time.monotonic() >= deadline:
        raise TimeoutError("Document raster extraction timed out.")
