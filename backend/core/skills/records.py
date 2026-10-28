"""SoAI - Immutable validated skill package records [backend/core/skills/records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.files.file_identity import FileIdentity

__all__ = (
    "SkillManifest",
    "SkillResource",
    "SkillMember",
    "SkillPackage",
    "StagedSkillPackage",
    "StagedSkillCollection",
    "SkillCompatibilityProfile",
    "SkillPublicationLayout",
)


@dataclass(frozen=True, slots=True)
class SkillManifest:
    name: str
    description: str
    source: str
    instructions: str
    license: str | None
    compatibility: str | None
    metadata_json: str
    disable_model_invocation: bool
    user_invocable: bool
    extensions_json: str = "{}"


@dataclass(frozen=True, slots=True)
class SkillMember:
    path: str
    is_directory: bool
    content: bytes
    digest: str

    @property
    def resource(self) -> SkillResource:
        return SkillResource(self.path, self.is_directory, len(self.content), self.digest)


@dataclass(frozen=True, slots=True)
class SkillResource:
    path: str
    is_directory: bool
    size_bytes: int
    digest: str


@dataclass(frozen=True, slots=True)
class SkillCompatibilityProfile:
    content_json: str
    digest: str


@dataclass(frozen=True, slots=True)
class SkillPackage:
    manifest: SkillManifest
    members: tuple[SkillMember, ...]
    digest: str
    upload_digest: str
    size_bytes: int
    profile: SkillCompatibilityProfile | None = None
    supporting_members: tuple[SkillMember, ...] = ()


@dataclass(frozen=True, slots=True)
class StagedSkillPackage:
    source_root: str
    manifest: SkillManifest
    resources: tuple[SkillResource, ...]
    digest: str
    size_bytes: int
    content_name: str
    content_identity: FileIdentity
    profile: SkillCompatibilityProfile | None = None
    supporting_resources: tuple[SkillResource, ...] = ()


@dataclass(frozen=True, slots=True)
class SkillPublicationLayout:
    manifest_path: str
    digest: str
    supporting_digests: tuple[tuple[str, str], ...]
    executable_paths: tuple[str, ...] = ()
    plugin_root: str = ""


@dataclass(frozen=True, slots=True)
class StagedSkillCollection:
    directory: str
    directory_identity: tuple[int, int]
    upload_digest: str
    packages: tuple[StagedSkillPackage, ...]
