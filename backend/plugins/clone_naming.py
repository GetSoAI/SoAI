"""SoAI - Plugin clone naming utilities [backend/plugins/clone_naming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ast
import re

from core.errors.exceptions import ValidationError
from plugins.manifest.ast_contracts import get_plugin_class_node
from plugins.manifest.class_field_contract import PLUGIN_FIELD_ALIASES, PLUGIN_FIELD_NAME

__all__ = ()


def _assignment_value(node: ast.stmt, field_name: str) -> ast.expr | None:
    if isinstance(node, ast.Assign):
        if len(node.targets) != 1:
            return None
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == field_name:
            return node.value
        return None
    if isinstance(node, ast.AnnAssign):
        if isinstance(node.target, ast.Name) and node.target.id == field_name:
            return node.value
    return None


def _replace_expressions(
    source_content: str,
    replacements: list[tuple[ast.expr, bytes]],
) -> str:
    source_bytes = source_content.encode("utf-8")
    source_lines = source_bytes.splitlines(keepends=True)
    spans: list[tuple[int, int, bytes]] = []
    for expression, replacement in replacements:
        if expression.end_lineno is None or expression.end_col_offset is None:
            raise ValidationError("Plugin manifest expression has no source span.")
        start_offset = sum(len(line) for line in source_lines[: expression.lineno - 1])
        start_offset += expression.col_offset
        end_offset = sum(len(line) for line in source_lines[: expression.end_lineno - 1])
        end_offset += expression.end_col_offset
        spans.append((start_offset, end_offset, replacement))
    for start_offset, end_offset, replacement in sorted(spans, reverse=True):
        source_bytes = source_bytes[:start_offset] + replacement + source_bytes[end_offset:]
    return source_bytes.decode("utf-8")


def derive_clone_manifest(
    final_target_name: str,
    source_content: str,
) -> tuple[str, str]:
    plugin_class = get_plugin_class_node(ast.parse(source_content))
    name_expressions = [
        expression
        for node in plugin_class.body
        if (expression := _assignment_value(node, PLUGIN_FIELD_NAME)) is not None
    ]
    alias_expressions = [
        expression
        for node in plugin_class.body
        if (expression := _assignment_value(node, PLUGIN_FIELD_ALIASES)) is not None
    ]
    if not name_expressions:
        raise ValidationError("Missing required manifest field 'NAME'.")
    try:
        original_display_name = ast.literal_eval(name_expressions[-1])
    except (SyntaxError, ValueError) as exception:
        raise ValidationError("Plugin NAME must be a string literal.") from exception
    if not isinstance(original_display_name, str):
        raise ValidationError("Plugin NAME must be a string literal.")
    clone_suffix_match = re.search("(_clone_\\d+)$", final_target_name)
    clone_suffix = clone_suffix_match.group(1) if clone_suffix_match else f"_{final_target_name}"
    new_display_name = f"{original_display_name}{clone_suffix}"
    encoded_display_name = repr(new_display_name).encode("utf-8")
    replacements = [(expression, encoded_display_name) for expression in name_expressions]
    replacements.extend((expression, b"[]") for expression in alias_expressions)
    return (
        _replace_expressions(source_content, replacements),
        new_display_name,
    )
