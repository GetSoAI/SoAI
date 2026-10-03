"""SoAI - Target-specific atomic temporary names and recovery discovery [backend/core/filesystem/atomic_write_names.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
import re
import uuid
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.filesystem.component_limits import filesystem_component_limit, filesystem_component_size
from core.filesystem.path_coercion import coerce_path, normalize_filesystem_path

if TYPE_CHECKING:
    from core.filesystem.path_coercion import PathInput

__all__ = ("atomic_temporary_path", "atomic_text_write_temporary_paths")


def atomic_temporary_path(path: str, *, partial: bool = False) -> str:
    basename = os.path.basename(path)
    parent = os.path.dirname(path)
    identifier = uuid.uuid4().hex
    suffix = f".partial.{identifier}" if partial else f".tmp.{os.getpid()}.{identifier}"
    limit = filesystem_component_limit(parent)
    if filesystem_component_size(basename + suffix) <= limit:
        return os.path.join(parent, basename + suffix)
    bounded_suffix = (
        f".partial.bounded.{identifier}" if partial else f".tmp.{os.getpid()}.bounded.{identifier}"
    )
    digest = hashlib.sha256(basename.encode("utf-8", "surrogatepass")).hexdigest()
    bounded = f".soai-atomic-{digest}{bounded_suffix}"
    if filesystem_component_size(bounded) > limit:
        raise ValidationError("Atomic temporary name cannot fit the destination filesystem.")
    return os.path.join(parent, bounded)


def atomic_text_write_temporary_paths(path: PathInput) -> tuple[str, ...]:
    resolved = coerce_path(path)
    parent = os.path.dirname(resolved) or os.curdir
    basename = os.path.basename(resolved)
    digest = hashlib.sha256(basename.encode("utf-8", "surrogatepass")).hexdigest()
    pattern = re.compile(
        rf"(?:{re.escape(basename)}\.tmp\.[1-9][0-9]*\.[0-9a-f]{{32}}|\.soai-atomic-{digest}\.tmp\.[1-9][0-9]*\.bounded\.[0-9a-f]{{32}})"
    )
    with os.scandir(normalize_filesystem_path(parent)) as entries:
        return tuple(
            os.path.join(parent, entry.name) for entry in entries if pattern.fullmatch(entry.name)
        )
