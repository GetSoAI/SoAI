"""SoAI - MCP glob_files matching and sorting [backend/mcp/tools/glob_files_sorting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import heapq
import os
from dataclasses import dataclass
from fnmatch import fnmatch

from mcp.tools.error import MCPToolError

__all__ = (
    "GlobFilesSearchResult",
    "collect_glob_matches_sorted",
    "validate_glob_sort",
)


@dataclass(frozen=True, slots=True)
class GlobFilesSearchResult:
    matches: list[str]
    total_matches: int


@dataclass(frozen=True, slots=True)
class _GlobMatchCandidate:
    path: str
    relative_posix_path: str
    modified_time_ns: int


@dataclass(frozen=True, slots=True)
class _SortTextKey:
    descending: bool
    value: str

    def __lt__(self, other: _SortTextKey) -> bool:
        if self.descending != other.descending:
            return self.descending < other.descending
        if self.descending:
            return self.value > other.value
        return self.value < other.value


_GLOB_SORT_MODIFIED_DESC: str = "modified_desc"
_GLOB_SORT_MODIFIED_ASC: str = "modified_asc"
_GLOB_SORT_NAME_ASC: str = "name_asc"
_GLOB_SORT_NAME_DESC: str = "name_desc"

_SUPPORTED_GLOB_SORTS: tuple[str, ...] = (
    _GLOB_SORT_MODIFIED_DESC,
    _GLOB_SORT_MODIFIED_ASC,
    _GLOB_SORT_NAME_ASC,
    _GLOB_SORT_NAME_DESC,
)


def validate_glob_sort(sort: str) -> str:
    normalized_sort = str(sort or "").strip()
    if normalized_sort in _SUPPORTED_GLOB_SORTS:
        return normalized_sort
    supported_text = ", ".join(_SUPPORTED_GLOB_SORTS)
    raise ValueError(
        f"Unsupported sort: {normalized_sort or '(empty)'} (supported: {supported_text})",
    )


def _posix_relpath(path: str, *, root_dir: str) -> str:
    return os.path.relpath(path, root_dir).replace(os.sep, "/")


def _candidate_matches_patterns(
    *,
    candidate_path: str,
    candidate_relative_posix_path: str,
    patterns_to_try: list[str],
) -> bool:
    candidate_basename = os.path.basename(candidate_path)
    for pattern in patterns_to_try:
        if pattern and (
            fnmatch(candidate_relative_posix_path, pattern) or fnmatch(candidate_basename, pattern)
        ):
            return True
    return False


def _safe_modified_time_ns(path: str) -> int:
    try:
        return int(os.stat(path, follow_symlinks=False).st_mtime_ns)
    except OSError as exception:
        raise MCPToolError(
            -32603,
            f"Failed to stat path while sorting glob_files matches: {path} ({exception})",
        ) from exception


def _build_worst_key(candidate: _GlobMatchCandidate, *, sort: str) -> tuple[int, _SortTextKey]:
    relpath = candidate.relative_posix_path
    if sort == _GLOB_SORT_MODIFIED_DESC:
        return (candidate.modified_time_ns, _SortTextKey(descending=True, value=relpath))
    if sort == _GLOB_SORT_MODIFIED_ASC:
        return (-candidate.modified_time_ns, _SortTextKey(descending=True, value=relpath))
    if sort == _GLOB_SORT_NAME_ASC:
        return (0, _SortTextKey(descending=True, value=relpath))
    if sort == _GLOB_SORT_NAME_DESC:
        return (0, _SortTextKey(descending=False, value=relpath))
    raise ValueError(f"Unsupported sort: {sort}")


def _sort_candidates_for_output(
    candidates: list[_GlobMatchCandidate],
    *,
    sort: str,
) -> list[_GlobMatchCandidate]:
    if sort == _GLOB_SORT_MODIFIED_DESC:
        return sorted(
            candidates,
            key=lambda item: (-item.modified_time_ns, item.relative_posix_path),
        )
    if sort == _GLOB_SORT_MODIFIED_ASC:
        return sorted(
            candidates,
            key=lambda item: (item.modified_time_ns, item.relative_posix_path),
        )
    if sort == _GLOB_SORT_NAME_ASC:
        return sorted(candidates, key=lambda item: item.relative_posix_path)
    if sort == _GLOB_SORT_NAME_DESC:
        return sorted(candidates, key=lambda item: item.relative_posix_path, reverse=True)
    raise ValueError(f"Unsupported sort: {sort}")


def collect_glob_matches_sorted(
    *,
    root_dir: str,
    patterns_to_try: list[str],
    limit: int,
    sort: str,
) -> GlobFilesSearchResult:
    validated_sort = validate_glob_sort(sort)
    normalized_limit = max(1, int(limit))
    requires_modified_time = validated_sort in (
        _GLOB_SORT_MODIFIED_DESC,
        _GLOB_SORT_MODIFIED_ASC,
    )

    best_heap: list[tuple[tuple[int, _SortTextKey], _GlobMatchCandidate]] = []
    total_matches = 0

    def consider_candidate(path: str) -> None:
        nonlocal total_matches
        relative = _posix_relpath(path, root_dir=root_dir)
        if not _candidate_matches_patterns(
            candidate_path=path,
            candidate_relative_posix_path=relative,
            patterns_to_try=patterns_to_try,
        ):
            return
        modified_time_ns = _safe_modified_time_ns(path) if requires_modified_time else 0
        candidate = _GlobMatchCandidate(
            path=path,
            relative_posix_path=relative,
            modified_time_ns=modified_time_ns,
        )
        total_matches += 1
        worst_key = _build_worst_key(candidate, sort=validated_sort)
        if len(best_heap) < normalized_limit:
            heapq.heappush(best_heap, (worst_key, candidate))
            return
        if worst_key > best_heap[0][0]:
            heapq.heapreplace(best_heap, (worst_key, candidate))

    for current_root, dir_names, file_names in os.walk(root_dir, followlinks=False):
        dir_names.sort()
        file_names.sort()

        for dir_name in dir_names:
            consider_candidate(os.path.join(current_root, dir_name))

        for file_name in file_names:
            consider_candidate(os.path.join(current_root, file_name))

    selected = [candidate for _, candidate in best_heap]
    ordered = _sort_candidates_for_output(selected, sort=validated_sort)
    return GlobFilesSearchResult(
        matches=[candidate.path for candidate in ordered],
        total_matches=total_matches,
    )
