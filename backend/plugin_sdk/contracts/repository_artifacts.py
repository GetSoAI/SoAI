"""SoAI - Plugin SDK repository artifact helpers [backend/plugin_sdk/contracts/repository_artifacts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import re

from core.plugins.sdk_public_exports import REPOSITORY_ARTIFACT_EXPORTS
from plugin_sdk.contracts.model_artifacts import build_artifact_directory_name
from plugin_sdk.contracts.safe_paths import safe_join_under_base

__all__ = REPOSITORY_ARTIFACT_EXPORTS


def build_repository_artifact_model_identifier(
    repository_id: str,
    revision: str,
    artifact_directory_name: str,
    *,
    file_suffix: str,
) -> str:
    repository_segments = _normalize_repository_segments(repository_id)
    artifact_name = build_artifact_directory_name(
        artifact_directory_name,
        file_suffix=file_suffix,
    )
    revision_token = _normalize_revision_token(revision)
    repository_identifier = "/".join(repository_segments)
    if revision_token is None:
        return f"{repository_identifier}/{artifact_name}"
    return f"{repository_identifier}@{revision_token}/{artifact_name}"


def build_repository_artifact_directory(
    base_dir: str,
    provider_segment: str,
    repository_id: str,
    revision: str,
    artifact_directory_name: str,
    *,
    file_suffix: str,
    description: str,
) -> str:
    repository_segments = _normalize_repository_segments(repository_id)
    artifact_name = build_artifact_directory_name(
        artifact_directory_name,
        file_suffix=file_suffix,
    )
    revision_token = _normalize_revision_token(revision)
    relative_segments = [_slug_component(provider_segment), *repository_segments[:-1]]
    leaf_segment = repository_segments[-1]
    if revision_token is not None:
        leaf_segment = f"{leaf_segment}@{revision_token}"
    relative_segments.append(leaf_segment)
    relative_segments.append(artifact_name)
    relative_path = os.path.join(*relative_segments)
    return safe_join_under_base(
        base_dir=base_dir,
        relative_path=relative_path,
        description=description,
    )


def resolve_repository_artifact_model_identifier(
    relative_path: str,
    *,
    provider_segment: str,
    repository_id: str | None = None,
    revision: str | None = None,
    file_suffix: str,
) -> str | None:
    if isinstance(repository_id, str) and repository_id.strip():
        return build_repository_artifact_model_identifier(
            repository_id.strip(),
            revision.strip() if isinstance(revision, str) else "",
            os.path.basename(relative_path),
            file_suffix=file_suffix,
        )
    normalized_relative_path = str(relative_path or "").replace("\\", "/").strip("/")
    segments = [segment for segment in normalized_relative_path.split("/") if segment]
    if len(segments) < 4 or segments[0] != _slug_component(provider_segment):
        return None
    repository_segments = list(segments[1:-1])
    detected_revision = ""
    leaf_segment = repository_segments[-1]
    if "@" in leaf_segment:
        base_segment, revision_segment = leaf_segment.rsplit("@", 1)
        if base_segment and revision_segment:
            repository_segments[-1] = base_segment
            detected_revision = revision_segment
    elif leaf_segment.lower() in {"main", "master"} and len(repository_segments) >= 2:
        detected_revision = leaf_segment
        repository_segments = repository_segments[:-1]
    if len(repository_segments) == 1 and "--" in repository_segments[0]:
        namespace, repository_name = repository_segments[0].split("--", 1)
        if namespace and repository_name:
            repository_segments = [namespace, repository_name]
    if not repository_segments:
        return None
    effective_revision = (
        revision.strip() if isinstance(revision, str) and revision.strip() else detected_revision
    )
    return build_repository_artifact_model_identifier(
        "/".join(repository_segments),
        effective_revision,
        segments[-1],
        file_suffix=file_suffix,
    )


def _normalize_repository_segments(repository_id: str) -> tuple[str, ...]:
    raw_segments = [
        segment for segment in str(repository_id or "").replace("\\", "/").split("/") if segment
    ]
    normalized_segments = tuple(_slug_component(segment) for segment in raw_segments)
    if len(normalized_segments) < 2:
        raise ValueError("repository_id must include a namespace and repository name.")
    return normalized_segments


def _normalize_revision_token(revision: str) -> str | None:
    normalized_revision = _slug_component(revision)
    if normalized_revision.lower() in {"default", "main", "master"}:
        return None
    return normalized_revision


def _slug_component(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", (value or "").strip())
    stripped = normalized.strip("._-")
    return stripped or "default"
