"""SoAI - Media job scratch storage ownership [backend/core/media/job_storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass

from core.config.protocols import ConfigProtocol
from core.files.upload_policy import resolve_temp_directory_runtime

__all__ = (
    "MediaJobPaths",
    "build_media_job_paths",
    "build_media_scratch_directory",
    "ensure_secure_directory",
    "remove_media_file",
    "remove_media_tree",
)


@dataclass(frozen=True, slots=True)
class MediaJobPaths:
    job_root: str
    frames_dir: str
    audio_dir: str


def build_media_job_paths(config: ConfigProtocol, namespace: str, job_id: str) -> MediaJobPaths:
    job_root = os.path.join(resolve_temp_directory_runtime(config), namespace, "jobs", job_id)
    return MediaJobPaths(
        job_root=job_root,
        frames_dir=os.path.join(job_root, "frames"),
        audio_dir=os.path.join(job_root, "audio"),
    )


def build_media_scratch_directory(job_paths: MediaJobPaths, scope_id: str) -> str:
    return os.path.join(job_paths.job_root, "scratch", scope_id)


def ensure_secure_directory(path: str) -> None:
    os.makedirs(path, mode=0o700, exist_ok=True)


def remove_media_file(path: str) -> bool:
    try:
        os.remove(path)
    except FileNotFoundError:
        return False
    return True


def remove_media_tree(path: str) -> bool:
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        return False
    return True
