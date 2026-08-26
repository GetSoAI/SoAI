"""SoAI - Plugin import boundary validation [backend/plugins/security.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ast

from core.errors.exceptions import SecurityError
from core.plugins.sdk_public_exports import PUBLIC_PLUGIN_SDK_EXPORTS
from plugins.import_dynamic_calls import (
    DYNAMIC_BUILTIN_CALLS,
    IMPORTLIB_MACHINERY_DYNAMIC_CALLS,
    IMPORTLIB_UTIL_DYNAMIC_FUNCTIONS,
    RUNPY_DYNAMIC_FUNCTIONS,
    DynamicImportCallAliases,
    collect_dynamic_call_violations,
)

__all__ = ("ensure_import_tree_has_no_forbidden_imports",)

FORBIDDEN_PLUGIN_MODULES: tuple[str, ...] = (
    "app",
    "core",
    "features",
    "database",
    "tasks",
    "plugins",
    "mcp",
    "orchestrator",
    "models",
    "metrics",
    "webui",
    "hardware",
    "files",
    "terminal",
    "backend",
)


def ensure_import_tree_has_no_forbidden_imports(
    plugin_name: str,
    tree: ast.Module,
) -> None:
    violations: set[str] = set()
    builtin_module_aliases: set[str] = set()
    builtin_function_aliases: dict[str, str] = {}
    importlib_aliases: set[str] = set()
    importlib_util_aliases: set[str] = set()
    importlib_machinery_aliases: set[str] = set()
    import_module_aliases: set[str] = set()
    importlib_util_function_aliases: set[str] = set()
    importlib_machinery_function_aliases: set[str] = set()
    runpy_aliases: set[str] = set()
    runpy_function_aliases: set[str] = set()
    plugin_sdk_aliases: set[str] = set()
    dynamic_aliases = DynamicImportCallAliases(
        builtin_module_aliases=builtin_module_aliases,
        builtin_function_aliases=builtin_function_aliases,
        importlib_aliases=importlib_aliases,
        importlib_util_aliases=importlib_util_aliases,
        importlib_machinery_aliases=importlib_machinery_aliases,
        import_module_aliases=import_module_aliases,
        importlib_util_function_aliases=importlib_util_function_aliases,
        importlib_machinery_function_aliases=importlib_machinery_function_aliases,
        runpy_aliases=runpy_aliases,
        runpy_function_aliases=runpy_function_aliases,
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            _collect_import_violations(
                node,
                violations,
                builtin_module_aliases,
                importlib_aliases,
                importlib_util_aliases,
                importlib_machinery_aliases,
                runpy_aliases,
                plugin_sdk_aliases,
            )
            continue
        if isinstance(node, ast.ImportFrom):
            _collect_import_from_violations(
                node,
                violations,
                builtin_function_aliases,
                import_module_aliases,
                importlib_util_aliases,
                importlib_machinery_aliases,
                importlib_util_function_aliases,
                importlib_machinery_function_aliases,
                runpy_function_aliases,
            )
            continue
        if isinstance(node, ast.Attribute):
            sdk_export = _plugin_sdk_attribute_export(node, plugin_sdk_aliases)
            if sdk_export is not None and sdk_export not in PUBLIC_PLUGIN_SDK_EXPORTS:
                violations.add(f"plugin_sdk.{sdk_export}")
            continue
        if isinstance(node, ast.Call):
            collect_dynamic_call_violations(
                node,
                violations,
                dynamic_aliases,
            )
    if violations:
        raise SecurityError(
            f"Plugin '{plugin_name}' imports forbidden modules: {', '.join(sorted(violations))}",
        )


def _collect_import_violations(
    node: ast.Import,
    violations: set[str],
    builtin_module_aliases: set[str],
    importlib_aliases: set[str],
    importlib_util_aliases: set[str],
    importlib_machinery_aliases: set[str],
    runpy_aliases: set[str],
    plugin_sdk_aliases: set[str],
) -> None:
    for alias in node.names:
        root = alias.name.split(".", 1)[0]
        if root in FORBIDDEN_PLUGIN_MODULES:
            violations.add(root)
        if alias.name.startswith("plugin_sdk."):
            violations.add("plugin_sdk.*")
        if alias.name == "plugin_sdk":
            plugin_sdk_aliases.add(alias.asname or "plugin_sdk")
        if alias.name == "builtins":
            builtin_module_aliases.add(alias.asname or "builtins")
        if alias.name == "importlib":
            importlib_aliases.add(alias.asname or "importlib")
        if alias.name == "importlib.util":
            importlib_aliases.add("importlib")
            importlib_util_aliases.add(alias.asname or "importlib.util")
        if alias.name == "importlib.machinery":
            importlib_aliases.add("importlib")
            importlib_machinery_aliases.add(alias.asname or "importlib.machinery")
        if alias.name == "runpy":
            runpy_aliases.add(alias.asname or "runpy")


def _plugin_sdk_attribute_export(
    node: ast.Attribute,
    plugin_sdk_aliases: set[str],
) -> str | None:
    attributes: list[str] = []
    value: ast.expr = node
    while isinstance(value, ast.Attribute):
        attributes.append(value.attr)
        value = value.value
    if not isinstance(value, ast.Name) or value.id not in plugin_sdk_aliases:
        return None
    if not attributes:
        return None
    return attributes[-1]


def _collect_import_from_violations(
    node: ast.ImportFrom,
    violations: set[str],
    builtin_function_aliases: dict[str, str],
    import_module_aliases: set[str],
    importlib_util_aliases: set[str],
    importlib_machinery_aliases: set[str],
    importlib_util_function_aliases: set[str],
    importlib_machinery_function_aliases: set[str],
    runpy_function_aliases: set[str],
) -> None:
    if node.level > 0:
        return
    module_name = node.module or ""
    module_root = module_name.split(".", 1)[0]
    if module_root in FORBIDDEN_PLUGIN_MODULES:
        violations.add(module_root)
    if module_name.startswith("plugin_sdk."):
        violations.add("plugin_sdk.*")
    if module_name == "plugin_sdk":
        for alias in node.names:
            if alias.name not in PUBLIC_PLUGIN_SDK_EXPORTS:
                violations.add(f"plugin_sdk.{alias.name}")
    if module_name == "builtins":
        for alias in node.names:
            if alias.name in DYNAMIC_BUILTIN_CALLS:
                builtin_function_aliases[alias.asname or alias.name] = alias.name
    if module_name == "importlib":
        for alias in node.names:
            if alias.name == "import_module":
                import_module_aliases.add(alias.asname or "import_module")
            if alias.name == "util":
                importlib_util_aliases.add(alias.asname or "util")
            if alias.name == "machinery":
                importlib_machinery_aliases.add(alias.asname or "machinery")
    if module_name == "importlib.util":
        for alias in node.names:
            if alias.name in IMPORTLIB_UTIL_DYNAMIC_FUNCTIONS:
                importlib_util_function_aliases.add(alias.asname or alias.name)
    if module_name == "importlib.machinery":
        for alias in node.names:
            if alias.name in IMPORTLIB_MACHINERY_DYNAMIC_CALLS:
                importlib_machinery_function_aliases.add(alias.asname or alias.name)
    if module_name == "runpy":
        for alias in node.names:
            if alias.name in RUNPY_DYNAMIC_FUNCTIONS:
                runpy_function_aliases.add(alias.asname or alias.name)
