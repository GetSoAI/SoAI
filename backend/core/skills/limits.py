"""SoAI - Skill package and owner storage limits [backend/core/skills/limits.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.archives.resource_limits import ArchiveResourceLimits
from core.types.json import JSONDict

__all__ = (
    "MAX_UPLOAD_BYTES",
    "MAX_DECODER_MEMORY_BYTES",
    "MAX_PACKAGE_BYTES",
    "MAX_FILES",
    "MAX_ENTRIES",
    "MAX_MANIFEST_BYTES",
    "MAX_PATH_DEPTH",
    "MAX_PATH_BYTES",
    "MAX_ENTRY_METADATA_BYTES",
    "MAX_ARCHIVE_METADATA_BYTES",
    "MAX_YAML_EVENTS",
    "MAX_YAML_DEPTH",
    "MAX_INSTALLED_SKILLS",
    "MAX_SELECTION_REQUEST_BYTES",
    "MAX_REPOSITORY_ENTRIES",
    "MAX_REPOSITORY_EXPANDED_BYTES",
    "MAX_REPOSITORY_METADATA_BYTES",
    "MAX_RETAINED_BYTES",
    "MAX_NAME_CHARACTERS",
    "MAX_DESCRIPTION_CHARACTERS",
    "MAX_COMPATIBILITY_CHARACTERS",
    "MAX_INVOCATION_ARGUMENT_CHARACTERS",
    "skill_archive_limits",
    "skill_repository_limits",
    "skill_library_limits",
)


MAX_DECODER_MEMORY_BYTES = 64 * 1024 * 1024
MAX_UPLOAD_BYTES = 250 * 1024 * 1024
MAX_PACKAGE_BYTES = 20 * 1024 * 1024
MAX_FILES = 256
MAX_ENTRIES = 512
MAX_MANIFEST_BYTES = 256 * 1024
MAX_PATH_DEPTH = 16
MAX_PATH_BYTES = 1024
MAX_ENTRY_METADATA_BYTES = 8 * 1024
MAX_ARCHIVE_METADATA_BYTES = 1024 * 1024
MAX_YAML_EVENTS = 4096
MAX_YAML_DEPTH = 16
MAX_INSTALLED_SKILLS = 500
MAX_SELECTION_REQUEST_BYTES = MAX_INSTALLED_SKILLS * 41 + 1024
MAX_REPOSITORY_ENTRIES = 65_536
MAX_REPOSITORY_EXPANDED_BYTES = 1024 * 1024 * 1024
MAX_REPOSITORY_METADATA_BYTES = 32 * 1024 * 1024
MAX_RETAINED_BYTES = 256 * 1024 * 1024
MAX_NAME_CHARACTERS = 64
MAX_DESCRIPTION_CHARACTERS = 2048
MAX_COMPATIBILITY_CHARACTERS = 500
MAX_INVOCATION_ARGUMENT_CHARACTERS = 256 * 1024


def skill_archive_limits() -> ArchiveResourceLimits:
    return ArchiveResourceLimits(
        max_members=MAX_ENTRIES,
        max_materialized_entries=MAX_ENTRIES,
        max_expanded_bytes=MAX_PACKAGE_BYTES,
        max_entry_metadata_bytes=MAX_ENTRY_METADATA_BYTES,
        max_aggregate_metadata_bytes=MAX_ARCHIVE_METADATA_BYTES,
    )


def skill_repository_limits() -> ArchiveResourceLimits:
    return ArchiveResourceLimits(
        max_members=MAX_REPOSITORY_ENTRIES,
        max_materialized_entries=MAX_REPOSITORY_ENTRIES,
        max_expanded_bytes=MAX_REPOSITORY_EXPANDED_BYTES,
        max_entry_metadata_bytes=MAX_ENTRY_METADATA_BYTES,
        max_aggregate_metadata_bytes=MAX_REPOSITORY_METADATA_BYTES,
    )


def skill_library_limits(*, upload_bytes: int = MAX_UPLOAD_BYTES) -> JSONDict:
    return {
        "installed_skills": MAX_INSTALLED_SKILLS,
        "retained_bytes": MAX_RETAINED_BYTES,
        "upload_bytes": min(MAX_UPLOAD_BYTES, upload_bytes),
        "package_bytes": MAX_PACKAGE_BYTES,
    }
