"""SoAI - Root-scoped path containment enforcement helpers [backend/core/files/path_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

__all__ = (
    "ensure_path_within_base",
    "ensure_path_within_base_lexical",
    "is_path_inside_directory",
    "is_path_overlap_with_base",
    "is_path_within_any_base",
    "is_path_within_base",
    "is_same_path",
    "safe_join_relative_under_base",
    "safe_join_relative_under_base_lexical",
)


def _normalize_for_relationship(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def is_same_path(left_path: str, right_path: str) -> bool:
    return _normalize_for_relationship(left_path) == _normalize_for_relationship(right_path)


def is_path_inside_directory(directory_path: str, candidate_path: str) -> bool:
    normalized_directory = _normalize_for_relationship(directory_path)
    normalized_candidate = _normalize_for_relationship(candidate_path)
    try:
        common_path = os.path.commonpath([normalized_directory, normalized_candidate])
    except ValueError:
        return False
    return common_path == normalized_directory


def is_path_within_base(base_path: str, candidate_path: str) -> bool:
    if not base_path:
        return False
    try:
        base_real = os.path.realpath(os.path.abspath(base_path))
        candidate_real = os.path.realpath(os.path.abspath(candidate_path))
        return os.path.commonpath([base_real, candidate_real]) == base_real
    except ValueError:
        return False


def is_path_within_any_base(base_paths: list[str], candidate_path: str) -> bool:
    for base_path in base_paths:
        if is_path_within_base(base_path, candidate_path):
            return True
    return False


def is_path_overlap_with_base(base_path: str, candidate_path: str) -> bool:
    if not base_path or not candidate_path:
        return False
    return is_path_within_base(base_path, candidate_path) or is_path_within_base(
        base_path=candidate_path,
        candidate_path=base_path,
    )


def ensure_path_within_base(
    base_path: str,
    candidate_path: str,
    *,
    description: str,
    error_cls: type[Exception] = ValueError,
) -> str:
    if not base_path:
        raise error_cls(f"{description} base path is not configured.")
    base_real = os.path.realpath(os.path.abspath(base_path))
    candidate_real = os.path.realpath(os.path.abspath(candidate_path))
    try:
        common = os.path.commonpath([base_real, candidate_real])
    except ValueError as exception:
        raise error_cls(
            f"{description} '{candidate_path}' is not located within '{base_path}'.",
        ) from exception
    if common != base_real:
        raise error_cls(f"{description} '{candidate_path}' escapes '{base_path}'.")
    return candidate_real


def ensure_path_within_base_lexical(
    base_path: str,
    candidate_path: str,
    *,
    description: str,
    error_cls: type[Exception] = ValueError,
) -> str:
    if not base_path:
        raise error_cls(f"{description} base path is not configured.")
    base_abs = os.path.abspath(base_path)
    candidate_abs = os.path.abspath(candidate_path)
    try:
        common = os.path.commonpath([base_abs, candidate_abs])
    except ValueError as exception:
        raise error_cls(
            f"{description} '{candidate_path}' is not located within '{base_path}'.",
        ) from exception
    if common != base_abs:
        raise error_cls(f"{description} '{candidate_path}' escapes '{base_path}'.")
    return candidate_abs


def safe_join_relative_under_base_lexical(
    *,
    base_path: str,
    relative_path: str,
    description: str,
    error_cls: type[Exception] = ValueError,
    base_error_message: str | None = None,
    relative_error_message: str | None = None,
    absolute_error_message: str | None = None,
) -> str:
    if not base_path.strip():
        raise error_cls(base_error_message or f"{description} base path is not configured.")
    if not relative_path.strip():
        raise error_cls(relative_error_message or f"{description} relative path is required.")
    if os.path.isabs(relative_path):
        raise error_cls(
            absolute_error_message or f"{description} absolute paths are not permitted.",
        )
    base_abs = os.path.abspath(base_path)
    candidate = os.path.abspath(os.path.join(base_abs, relative_path))
    return ensure_path_within_base_lexical(
        base_abs,
        candidate,
        description=description,
        error_cls=error_cls,
    )


def safe_join_relative_under_base(
    *,
    base_path: str,
    relative_path: str,
    description: str,
    error_cls: type[Exception] = ValueError,
    base_error_message: str | None = None,
    relative_error_message: str | None = None,
    absolute_error_message: str | None = None,
) -> str:
    if not base_path.strip():
        raise error_cls(base_error_message or f"{description} base path is not configured.")
    if not relative_path.strip():
        raise error_cls(relative_error_message or f"{description} relative path is required.")
    if os.path.isabs(relative_path):
        raise error_cls(
            absolute_error_message or f"{description} absolute paths are not permitted.",
        )
    base_real = os.path.realpath(base_path)
    candidate = os.path.realpath(os.path.join(base_real, relative_path))
    return ensure_path_within_base(
        base_real,
        candidate,
        description=description,
        error_cls=error_cls,
    )
