"""SoAI - Playwright browser artifact state: expected revisions, readiness, pruning [backend/core/bootstrap/playwright_browser_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import platform
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib.util import find_spec

from core.errors.exceptions import ValidationError
from core.serialization.json_parsing import parse_json_value

__all__ = (
    "BrowserPruneOutcome",
    "is_expected_chromium_installed",
    "prune_stale_browser_directories",
    "read_expected_browser_directory_names",
)

_EXPECTED_BROWSER_NAMES: frozenset[str] = frozenset(
    {"chromium", "chromium-headless-shell", "ffmpeg"},
)
_READINESS_BROWSER_NAMES: tuple[str, ...] = ("chromium", "chromium-headless-shell")
_PRUNE_PREFIXES: tuple[str, ...] = ("chromium-", "chromium_headless_shell-", "ffmpeg-")
_INSTALLATION_MARKER_NAME = "INSTALLATION_COMPLETE"
_EXECUTABLE_SEARCH_MAX_DEPTH = 4


@dataclass(frozen=True, slots=True)
class BrowserPruneOutcome:
    removed_directories: tuple[str, ...]
    failed_directories: tuple[str, ...]


def _resolve_browsers_manifest_path() -> str | None:
    try:
        spec = find_spec("playwright")
    except (ImportError, ValueError):
        spec = None
    if spec is None:
        return None
    origin = spec.origin
    if not isinstance(origin, str) or not origin.strip():
        return None
    return os.path.join(os.path.dirname(origin), "driver", "package", "browsers.json")


def _read_expected_revisions() -> dict[str, str]:
    manifest_path = _resolve_browsers_manifest_path()
    if manifest_path is None:
        return {}
    raw_manifest_text: str | None
    try:
        with open(manifest_path, encoding="utf-8", errors="strict") as manifest_file:
            raw_manifest_text = manifest_file.read()
    except (OSError, UnicodeDecodeError):
        raw_manifest_text = None
    if raw_manifest_text is None:
        return {}
    try:
        payload = parse_json_value(raw_manifest_text, field="playwright browsers manifest")
    except ValidationError:
        payload = None
    if not isinstance(payload, Mapping):
        return {}
    browsers_value = payload.get("browsers")
    if not isinstance(browsers_value, Sequence) or isinstance(browsers_value, str):
        return {}
    revisions: dict[str, str] = {}
    for browser_entry in browsers_value:
        if not isinstance(browser_entry, Mapping):
            continue
        name_value = browser_entry.get("name")
        revision_value = browser_entry.get("revision")
        if not isinstance(name_value, str) or name_value not in _EXPECTED_BROWSER_NAMES:
            continue
        if not isinstance(revision_value, str) or not revision_value.strip():
            continue
        revisions[name_value] = revision_value.strip()
    return revisions


def _directory_name_for_browser(browser_name: str, revision: str) -> str:
    return f"{browser_name.replace('-', '_')}-{revision}"


def read_expected_browser_directory_names() -> tuple[str, ...]:
    revisions = _read_expected_revisions()
    return tuple(
        _directory_name_for_browser(browser_name, revision)
        for browser_name, revision in sorted(revisions.items())
    )


def _readiness_expectations() -> tuple[tuple[str, str], ...]:
    revisions = _read_expected_revisions()
    expectations: list[tuple[str, str]] = []
    for browser_name in _READINESS_BROWSER_NAMES:
        revision = revisions.get(browser_name)
        if revision is None:
            return ()
        expectations.append(
            (browser_name, _directory_name_for_browser(browser_name, revision)),
        )
    return tuple(expectations)


def _executable_basenames_for_browser(browser_name: str) -> frozenset[str]:
    system_name = platform.system()
    if browser_name == "chromium":
        if system_name == "Windows":
            return frozenset({"chrome.exe"})
        if system_name == "Darwin":
            return frozenset({"Chromium"})
        return frozenset({"chrome"})
    if browser_name == "chromium-headless-shell":
        if system_name == "Windows":
            return frozenset({"chrome-headless-shell.exe", "headless_shell.exe"})
        return frozenset({"chrome-headless-shell", "headless_shell"})
    return frozenset()


def _directory_contains_executable(revision_path: str, basenames: frozenset[str]) -> bool:
    if not basenames:
        return False
    resolved_revision_path = os.path.abspath(revision_path)
    base_depth = resolved_revision_path.rstrip(os.sep).count(os.sep)
    for current_root, child_directories, file_names in os.walk(resolved_revision_path):
        current_depth = current_root.rstrip(os.sep).count(os.sep) - base_depth
        if current_depth >= _EXECUTABLE_SEARCH_MAX_DEPTH:
            child_directories.clear()
        for file_name in file_names:
            if file_name in basenames and os.path.isfile(os.path.join(current_root, file_name)):
                return True
    return False


def _expected_chromium_installation_present(browsers_path: str) -> bool:
    if not os.path.isdir(browsers_path):
        return False
    expectations = _readiness_expectations()
    if not expectations:
        return False
    for browser_name, directory_name in expectations:
        revision_path = os.path.join(browsers_path, directory_name)
        if not os.path.isdir(revision_path):
            return False
        if not os.path.isfile(os.path.join(revision_path, _INSTALLATION_MARKER_NAME)):
            return False
        executable_basenames = _executable_basenames_for_browser(browser_name)
        if not _directory_contains_executable(revision_path, executable_basenames):
            return False
    return True


def is_expected_chromium_installed(*, browsers_path: str) -> bool:
    if not isinstance(browsers_path, str) or not browsers_path.strip():
        return False
    try:
        installed = _expected_chromium_installation_present(browsers_path)
    except OSError:
        installed = False
    return installed


def prune_stale_browser_directories(*, browsers_path: str) -> BrowserPruneOutcome:
    empty_outcome = BrowserPruneOutcome(removed_directories=(), failed_directories=())
    if not isinstance(browsers_path, str) or not browsers_path.strip():
        return empty_outcome
    resolved_root = os.path.realpath(browsers_path)
    if not os.path.isdir(resolved_root):
        return empty_outcome
    expected_names = frozenset(read_expected_browser_directory_names())
    if not expected_names:
        return empty_outcome
    entry_names: list[str]
    try:
        entry_names = sorted(os.listdir(resolved_root))
    except OSError:
        entry_names = []
    removed_directories: list[str] = []
    failed_directories: list[str] = []
    for entry_name in entry_names:
        if not entry_name.startswith(_PRUNE_PREFIXES):
            continue
        if entry_name in expected_names:
            continue
        entry_path = os.path.join(resolved_root, entry_name)
        if os.path.islink(entry_path) or not os.path.isdir(entry_path):
            continue
        try:
            shutil.rmtree(entry_path)
            removed_directories.append(entry_name)
        except OSError:
            failed_directories.append(entry_name)
    return BrowserPruneOutcome(
        removed_directories=tuple(removed_directories),
        failed_directories=tuple(failed_directories),
    )
