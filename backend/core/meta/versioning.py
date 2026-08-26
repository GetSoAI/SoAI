"""SoAI - Semantic version parsing and comparison utilities [backend/core/meta/versioning.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, override

from packaging.version import InvalidVersion, Version

from core.errors.exceptions import ValidationError
from core.meta.version import __version__

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "NormalizedVersion",
    "build_update_status",
    "extract_release_version",
    "get_core_version",
    "is_newer_version",
    "normalize_version_string",
    "parse_semantic_version",
)


def normalize_version_string(raw_version: str) -> str:
    if not isinstance(raw_version, str):
        raise ValidationError("Version string must be provided as text.")
    normalized = raw_version.strip()
    if not normalized:
        raise ValidationError("Version string cannot be empty.")
    normalized = normalized.lstrip("vV")
    if not normalized:
        raise ValidationError("Version string cannot be empty after removing prefix.")
    return normalized


class NormalizedVersion(Version):

    @override
    def __str__(self) -> str:
        base = super().__str__()
        if not self.release:
            return base
        if self.pre or self.post or self.dev or self.local:
            return base
        release_parts = list(self.release)
        while len(release_parts) > 2 and release_parts[-1] == 0:
            release_parts.pop()
        if len(release_parts) == 1:
            return str(release_parts[0])
        return ".".join(str(part) for part in release_parts)


def parse_semantic_version(raw_version: str) -> NormalizedVersion:
    normalized = normalize_version_string(raw_version)
    try:
        return NormalizedVersion(normalized)
    except InvalidVersion as exception:
        raise ValidationError(f"Invalid version string: {raw_version}") from exception


def is_newer_version(latest_version: str, reference_version: str) -> bool:
    latest = parse_semantic_version(latest_version)
    reference = parse_semantic_version(reference_version)
    return latest > reference


def extract_release_version(release_info: Mapping[str, JSONValue]) -> str:
    if not isinstance(release_info, Mapping):
        raise ValidationError("Release information must be a mapping.")
    tag_value = release_info.get("tag_name")
    if not isinstance(tag_value, str):
        raise ValidationError("Release information missing a textual 'tag_name'.")
    return normalize_version_string(tag_value)


def build_update_status(
    raw_current_version: str | None,
    release_info: Mapping[str, JSONValue],
) -> JSONDict:
    if raw_current_version is None:
        raise ValidationError("Current core version is unavailable.")
    current_version = normalize_version_string(raw_current_version)
    latest_version = extract_release_version(release_info)
    update_available = is_newer_version(latest_version, current_version)
    return {
        "current_version": current_version,
        "latest_version": latest_version,
        "update_available": update_available,
        "release_url": release_info.get("html_url"),
        "published_at": release_info.get("published_at"),
        "release_notes": release_info.get("body"),
    }


def get_core_version() -> str:
    return __version__
