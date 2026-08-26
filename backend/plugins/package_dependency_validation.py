"""SoAI - Plugin package dependency validation [backend/plugins/package_dependency_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ast
import re
import sys
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, distribution

from packaging.requirements import InvalidRequirement, Requirement

from core.errors.exceptions import SecurityError
from plugins.environments.baseline import read_plugin_worker_baseline_package_names

__all__ = ("ensure_declared_package_dependencies",)


def _normalize_package_name(value: str) -> str:
    candidate = re.sub(r"[-_.]+", "_", str(value or "").strip().lower())
    return candidate.strip("_")


def _declared_package_import_aliases(distribution_name: str) -> tuple[str, ...]:
    if distribution_name == "pyyaml":
        return ("yaml",)
    if distribution_name == "piper_tts":
        return ("piper",)
    return ()


def _collect_import_roots(tree: ast.Module) -> set[str]:
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0].strip()
                if root:
                    imported_roots.add(root)
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                continue
            module_name = str(node.module or "").strip()
            if not module_name:
                continue
            root = module_name.split(".", 1)[0].strip()
            if root:
                imported_roots.add(root)
    return imported_roots


def _is_stdlib_import_root(import_root: str) -> bool:
    return import_root in sys.stdlib_module_names or import_root == "__future__"


@lru_cache(maxsize=1)
def _baseline_distribution_names() -> frozenset[str]:
    return frozenset(
        _normalize_package_name(baseline_package_name)
        for baseline_package_name in read_plugin_worker_baseline_package_names()
        if _normalize_package_name(baseline_package_name)
    )


@lru_cache(maxsize=2048)
def _distribution_import_roots(distribution_name: str) -> frozenset[str]:
    normalized_distribution_name = _normalize_package_name(distribution_name)
    import_roots: set[str] = set()
    try:
        metadata = distribution(distribution_name)
    except PackageNotFoundError:
        metadata = None
    if metadata is not None:
        top_level_text = metadata.read_text("top_level.txt")
        if top_level_text is not None:
            for line in top_level_text.splitlines():
                normalized_import_root = _normalize_package_name(line)
                if normalized_import_root:
                    import_roots.add(normalized_import_root)
    if normalized_distribution_name:
        import_roots.add(normalized_distribution_name)
    return frozenset(import_roots)


@lru_cache(maxsize=1024)
def _resolve_declared_package_import_roots(packages: tuple[str, ...]) -> frozenset[str]:
    declared_distribution_names: set[str] = set(_baseline_distribution_names())
    declared_import_roots: set[str] = set()
    for package_spec in packages:
        candidate = str(package_spec or "").strip()
        if not candidate:
            continue
        try:
            requirement = Requirement(candidate)
            distribution_name = requirement.name
        except InvalidRequirement:
            distribution_name = candidate.split(";", 1)[0].strip()
        normalized_distribution_name = _normalize_package_name(distribution_name)
        if not normalized_distribution_name:
            continue
        declared_distribution_names.add(normalized_distribution_name)
        declared_import_roots.add(normalized_distribution_name)
        for alias in _declared_package_import_aliases(normalized_distribution_name):
            normalized_alias = _normalize_package_name(alias)
            if normalized_alias:
                declared_import_roots.add(normalized_alias)
    for distribution_name in declared_distribution_names:
        declared_import_roots.update(_distribution_import_roots(distribution_name))
    return frozenset(declared_import_roots)


def ensure_declared_package_dependencies(
    plugin_name: str,
    tree: ast.Module,
    packages: list[str],
) -> None:
    declared_import_roots = _resolve_declared_package_import_roots(tuple(packages))
    undeclared_imports = sorted(
        _normalize_package_name(import_root)
        for import_root in _collect_import_roots(tree)
        if not _is_stdlib_import_root(import_root)
        and import_root != "plugin_sdk"
        and _normalize_package_name(import_root) not in declared_import_roots
    )
    if undeclared_imports:
        raise SecurityError(
            f"Plugin '{plugin_name}' imports third-party modules without matching PACKAGE_DEPENDENCIES: "
            + ", ".join(undeclared_imports),
        )
