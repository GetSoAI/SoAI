"""SoAI - Bootstrap file helpers (stdlib-only) [backend/core/bootstrap/files.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
import uuid
from functools import partial

__all__ = (
    "compute_sha3_256",
    "compute_sha256",
    "compute_sha512",
    "compute_source_directory_sha256",
    "read_text_file",
    "write_text_file_atomic",
)

BOOTSTRAP_FILE_HASH_CHUNK_BYTES = 1_048_576


def _compute_file_hash(path: str | os.PathLike[str], algorithm: str) -> str:
    resolved_path = os.fspath(path)
    digest = hashlib.new(algorithm)
    with open(resolved_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(BOOTSTRAP_FILE_HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_sha256(path: str | os.PathLike[str]) -> str:
    return _compute_file_hash(path, "sha256")


def compute_sha3_256(path: str | os.PathLike[str]) -> str:
    return _compute_file_hash(path, "sha3_256")


def compute_sha512(path: str | os.PathLike[str]) -> str:
    return _compute_file_hash(path, "sha512")


def compute_source_directory_sha256(path: str | os.PathLike[str]) -> str:
    resolved_path = os.fspath(path)
    digest = hashlib.sha256()
    if not os.path.isdir(resolved_path):
        raise FileNotFoundError(f"Required directory does not exist: {resolved_path}")
    for root, dir_names, file_names in os.walk(resolved_path):
        dir_names[:] = sorted(name for name in dir_names if name != "__pycache__")
        source_file_names = sorted(
            name for name in file_names if not name.endswith((".pyc", ".pyo"))
        )
        for file_name in source_file_names:
            file_path = os.path.join(root, file_name)
            relative_path = os.path.relpath(file_path, resolved_path).replace(os.sep, "/")
            digest.update(relative_path.encode("utf-8"))
            digest.update(b"\0")
            with open(file_path, "rb") as handle:
                for chunk in iter(partial(handle.read, BOOTSTRAP_FILE_HASH_CHUNK_BYTES), b""):
                    digest.update(chunk)
            digest.update(b"\0")
    return digest.hexdigest()


def read_text_file(path: str | os.PathLike[str]) -> str | None:
    resolved_path = os.fspath(path)
    if not os.path.isfile(resolved_path):
        return None
    content: str | None = None
    try:
        with open(resolved_path, encoding="utf-8", errors="strict") as handle:
            content = handle.read().strip()
    except OSError:
        content = None
    return content


def write_text_file_atomic(
    path: str | os.PathLike[str],
    content: str,
    *,
    file_mode: int | None = None,
) -> None:
    resolved_path = os.fspath(path)
    parent = os.path.dirname(resolved_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    temp_path = f"{resolved_path}.tmp.{os.getpid()}.{uuid.uuid4().hex}"
    try:
        descriptor = os.open(
            temp_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            file_mode if file_mode is not None else 0o666,
        )
        if file_mode is not None and os.name != "nt":
            try:
                os.fchmod(descriptor, file_mode)
            except OSError:
                os.close(descriptor)
                raise
        with os.fdopen(descriptor, "w", encoding="utf-8", errors="strict") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, resolved_path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
