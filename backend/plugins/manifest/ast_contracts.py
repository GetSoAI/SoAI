"""SoAI - AST manifest contract parsing helpers [backend/plugins/manifest/ast_contracts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ast

from core.errors.exceptions import ValidationError
from core.openai.capability_taxonomy import OPENAI_FEATURE_MATRIX
from core.openai.compatibility import ExternalProviderMode
from core.types.json import JSONValue
from plugins.manifest.class_field_contract import PLUGIN_FIELD_EXTERNAL_PROVIDER_MODE

__all__ = (
    "MANIFEST_CLASS_NAME",
    "eval_external_provider_mode",
    "eval_openai_flags",
    "eval_required_bool",
    "eval_required_literal",
    "extract_class_assignments",
    "get_plugin_class_node",
)

MANIFEST_CLASS_NAME = "Plugin"
_EXTERNAL_PROVIDER_MODE_PATHS: frozenset[tuple[str, ...]] = frozenset(
    {
        ("plugin_sdk", "ExternalProviderMode"),
        ("ExternalProviderMode",),
    },
)


def get_plugin_class_node(tree: ast.Module) -> ast.ClassDef:
    class_nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == MANIFEST_CLASS_NAME
    ]
    if not class_nodes:
        raise ValidationError(f"Missing required class '{MANIFEST_CLASS_NAME}'.")
    if len(class_nodes) != 1:
        raise ValidationError(
            f"Plugin entrypoint must declare exactly one direct class '{MANIFEST_CLASS_NAME}'.",
        )
    return class_nodes[0]


def extract_class_assignments(class_node: ast.ClassDef) -> dict[str, ast.expr]:
    assignments: dict[str, ast.expr] = {}
    for node in class_node.body:
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1:
                continue
            target = node.targets[0]
            if isinstance(target, ast.Name) and isinstance(node.value, ast.expr):
                assignments[target.id] = node.value
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            value = node.value
            if isinstance(target, ast.Name) and isinstance(value, ast.expr):
                assignments[target.id] = value
    return assignments


def _eval_literal(node: ast.expr, *, field_name: str) -> JSONValue:
    if isinstance(node, ast.Constant):
        value = node.value
        if value is None or isinstance(value, str | int | float | bool):
            return value
        raise ValidationError(f"Manifest field '{field_name}' must be a JSON-compatible literal.")
    if isinstance(node, ast.List | ast.Tuple | ast.Set):
        list_payload: list[JSONValue] = []
        for item in node.elts:
            if isinstance(item, ast.expr):
                list_payload.append(_eval_literal(item, field_name=field_name))
        return list_payload
    if isinstance(node, ast.Dict):
        dict_payload: dict[str, JSONValue] = {}
        for key_node, value_node in zip(node.keys, node.values, strict=False):
            if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
                raise ValidationError(f"Manifest field '{field_name}' dict keys must be strings.")
            if not isinstance(value_node, ast.expr):
                raise ValidationError(f"Manifest field '{field_name}' must be a literal.")
            dict_payload[key_node.value] = _eval_literal(value_node, field_name=field_name)
        return dict_payload
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.USub)
        and isinstance(node.operand, ast.Constant)
    ):
        value = node.operand.value
        if isinstance(value, int | float):
            return -value
    raise ValidationError(f"Manifest field '{field_name}' must be a literal.")


def _require_assignment(assignments: dict[str, ast.expr], key: str) -> ast.expr:
    node = assignments.get(key)
    if node is None:
        raise ValidationError(f"Missing required manifest field '{key}'.")
    return node


def eval_required_literal(assignments: dict[str, ast.expr], key: str) -> JSONValue:
    node = _require_assignment(assignments, key)
    return _eval_literal(node, field_name=key)


def eval_required_bool(assignments: dict[str, ast.expr], key: str) -> bool:
    value = eval_required_literal(assignments, key)
    if isinstance(value, bool):
        return value
    raise ValidationError(f"Manifest field '{key}' must be a boolean.")


def _extract_attribute_path(node: ast.expr) -> tuple[str, ...] | None:
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, ast.Attribute):
        parent_path = _extract_attribute_path(node.value)
        if parent_path is None:
            return None
        return (*parent_path, node.attr)
    return None


def eval_external_provider_mode(assignments: dict[str, ast.expr]) -> str | None:
    node = _require_assignment(assignments, PLUGIN_FIELD_EXTERNAL_PROVIDER_MODE)
    if isinstance(node, ast.Attribute):
        attribute_path = _extract_attribute_path(node)
        if attribute_path is None or len(attribute_path) < 2:
            raise ValidationError(
                "Manifest field 'EXTERNAL_PROVIDER_MODE' must reference a valid external provider mode.",
            )
        path_root = attribute_path[:-1]
        attr_name = attribute_path[-1].strip()
        if path_root not in _EXTERNAL_PROVIDER_MODE_PATHS:
            raise ValidationError(
                "Manifest field 'EXTERNAL_PROVIDER_MODE' must reference a valid external provider mode.",
            )
        if attr_name in {mode.name for mode in ExternalProviderMode}:
            return attr_name
        raise ValidationError(
            "Manifest field 'EXTERNAL_PROVIDER_MODE' must reference a valid external provider mode.",
        )
    value = _eval_literal(node, field_name=PLUGIN_FIELD_EXTERNAL_PROVIDER_MODE)
    if value is None or isinstance(value, str):
        return value
    raise ValidationError(
        "Manifest field 'EXTERNAL_PROVIDER_MODE' must reference a valid external provider mode.",
    )


def eval_openai_flags(assignments: dict[str, ast.expr]) -> dict[str, bool]:
    flags: dict[str, bool] = {}
    for _section_name, entries in OPENAI_FEATURE_MATRIX:
        for _token, attr_name in entries:
            value = eval_required_literal(assignments, attr_name)
            if not isinstance(value, bool):
                raise ValidationError(f"Manifest field '{attr_name}' must be a boolean.")
            flags[attr_name] = value
    return flags
