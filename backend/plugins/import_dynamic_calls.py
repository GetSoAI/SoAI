"""SoAI - Plugin AST dynamic call import bypass detection [backend/plugins/import_dynamic_calls.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ast
from dataclasses import dataclass

__all__ = ("DynamicImportCallAliases", "collect_dynamic_call_violations")


@dataclass(frozen=True, slots=True)
class DynamicImportCallAliases:
    builtin_module_aliases: set[str]
    builtin_function_aliases: dict[str, str]
    importlib_aliases: set[str]
    importlib_util_aliases: set[str]
    importlib_machinery_aliases: set[str]
    import_module_aliases: set[str]
    importlib_util_function_aliases: set[str]
    importlib_machinery_function_aliases: set[str]
    runpy_aliases: set[str]
    runpy_function_aliases: set[str]


def collect_dynamic_call_violations(
    node: ast.Call,
    violations: set[str],
    aliases: DynamicImportCallAliases,
) -> None:
    if isinstance(node.func, ast.Name):
        if node.func.id == "getattr":
            _collect_getattr_dynamic_call_violations(
                node,
                violations,
                aliases=aliases,
            )
        if node.func.id in DYNAMIC_BUILTIN_CALLS:
            violations.add(node.func.id)
        builtin_name = aliases.builtin_function_aliases.get(node.func.id)
        if builtin_name is not None:
            violations.add(builtin_name)
        if node.func.id in aliases.import_module_aliases:
            violations.add("importlib.import_module")
        if node.func.id in aliases.importlib_util_function_aliases:
            violations.add(f"importlib.util.{node.func.id}")
        if node.func.id in aliases.importlib_machinery_function_aliases:
            violations.add(f"importlib.machinery.{node.func.id}")
        if node.func.id in aliases.runpy_function_aliases:
            violations.add(f"runpy.{node.func.id}")
        return
    dotted_name = _attribute_name(node.func)
    if not dotted_name:
        return
    if _is_importlib_import_module_call(dotted_name, aliases.importlib_aliases):
        violations.add("importlib.import_module")
    builtin_name = _builtin_dynamic_call_name(
        dotted_name,
        aliases.builtin_module_aliases,
    )
    if builtin_name is not None:
        violations.add(builtin_name)
    if _is_importlib_util_dynamic_call(
        dotted_name,
        aliases.importlib_aliases,
        aliases.importlib_util_aliases,
    ):
        violations.add(dotted_name)
    if _is_importlib_machinery_dynamic_call(
        dotted_name,
        aliases.importlib_aliases,
        aliases.importlib_machinery_aliases,
    ):
        violations.add(dotted_name)
    if _is_runpy_dynamic_call(dotted_name, aliases.runpy_aliases):
        violations.add(dotted_name)


def _collect_getattr_dynamic_call_violations(
    node: ast.Call,
    violations: set[str],
    *,
    aliases: DynamicImportCallAliases,
) -> None:
    if len(node.args) < 2:
        return
    target_name = _attribute_name(node.args[0])
    requested_name = node.args[1]
    if not target_name or not isinstance(requested_name, ast.Constant):
        return
    if not isinstance(requested_name.value, str):
        return
    symbol_name = requested_name.value
    for alias in aliases.importlib_aliases:
        if target_name == alias and symbol_name == "import_module":
            violations.add("importlib.import_module")
        if target_name == f"{alias}.util" and symbol_name in IMPORTLIB_UTIL_DYNAMIC_FUNCTIONS:
            violations.add(f"{target_name}.{symbol_name}")
        if target_name == f"{alias}.machinery" and symbol_name in IMPORTLIB_MACHINERY_DYNAMIC_CALLS:
            violations.add(f"{target_name}.{symbol_name}")
    for alias in aliases.importlib_util_aliases:
        if target_name == alias and symbol_name in IMPORTLIB_UTIL_DYNAMIC_FUNCTIONS:
            violations.add(f"{target_name}.{symbol_name}")
    for alias in aliases.importlib_machinery_aliases:
        if target_name == alias and symbol_name in IMPORTLIB_MACHINERY_DYNAMIC_CALLS:
            violations.add(f"{target_name}.{symbol_name}")
    for alias in aliases.runpy_aliases:
        if target_name == alias and symbol_name in RUNPY_DYNAMIC_FUNCTIONS:
            violations.add(f"{target_name}.{symbol_name}")


def _attribute_name(expression: ast.expr) -> str:
    if isinstance(expression, ast.Name):
        return expression.id
    if isinstance(expression, ast.Attribute):
        parent_name = _attribute_name(expression.value)
        if parent_name:
            return f"{parent_name}.{expression.attr}"
    return ""


def _is_importlib_import_module_call(dotted_name: str, importlib_aliases: set[str]) -> bool:
    for alias in importlib_aliases:
        if dotted_name == f"{alias}.import_module":
            return True
    return False


def _builtin_dynamic_call_name(
    dotted_name: str,
    builtin_module_aliases: set[str],
) -> str | None:
    for alias in builtin_module_aliases:
        for function_name in DYNAMIC_BUILTIN_CALLS:
            if dotted_name == f"{alias}.{function_name}":
                return function_name
    return None


def _is_importlib_util_dynamic_call(
    dotted_name: str,
    importlib_aliases: set[str],
    importlib_util_aliases: set[str],
) -> bool:
    for alias in importlib_aliases:
        for function_name in IMPORTLIB_UTIL_DYNAMIC_FUNCTIONS:
            if dotted_name == f"{alias}.util.{function_name}":
                return True
    for alias in importlib_util_aliases:
        for function_name in IMPORTLIB_UTIL_DYNAMIC_FUNCTIONS:
            if dotted_name == f"{alias}.{function_name}":
                return True
    return False


def _is_runpy_dynamic_call(dotted_name: str, runpy_aliases: set[str]) -> bool:
    for alias in runpy_aliases:
        for function_name in RUNPY_DYNAMIC_FUNCTIONS:
            if dotted_name == f"{alias}.{function_name}":
                return True
    return False


def _is_importlib_machinery_dynamic_call(
    dotted_name: str,
    importlib_aliases: set[str],
    importlib_machinery_aliases: set[str],
) -> bool:
    for alias in importlib_aliases:
        for function_name in IMPORTLIB_MACHINERY_DYNAMIC_CALLS:
            if dotted_name == f"{alias}.machinery.{function_name}":
                return True
    for alias in importlib_machinery_aliases:
        for function_name in IMPORTLIB_MACHINERY_DYNAMIC_CALLS:
            if dotted_name == f"{alias}.{function_name}":
                return True
    return False


DYNAMIC_BUILTIN_CALLS: frozenset[str] = frozenset(("__import__", "eval", "exec", "compile"))
IMPORTLIB_MACHINERY_DYNAMIC_CALLS: frozenset[str] = frozenset(
    (
        "ExtensionFileLoader",
        "FileFinder",
        "SourceFileLoader",
        "SourcelessFileLoader",
    ),
)
IMPORTLIB_UTIL_DYNAMIC_FUNCTIONS: frozenset[str] = frozenset(
    ("spec_from_file_location", "module_from_spec"),
)
RUNPY_DYNAMIC_FUNCTIONS: frozenset[str] = frozenset(("run_module", "run_path"))
