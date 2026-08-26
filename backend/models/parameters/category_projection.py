"""SoAI - Parameter category projection helpers [backend/models/parameters/category_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types.json import is_json_dict
from core.types.json_value import copy_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("copy_used_parameter_categories",)


def copy_used_parameter_categories(schema: JSONDict, plugin_categories: JSONDict) -> JSONDict:
    used_categories: set[str] = set()
    for definition in schema.values():
        if not is_json_dict(definition):
            continue
        category_value = definition.get("category")
        if isinstance(category_value, str) and category_value:
            used_categories.add(category_value)
    filtered_categories: JSONDict = {
        key: value
        for key, value in copy_json_dict(plugin_categories).items()
        if key in used_categories
    }
    for category in sorted(used_categories):
        if category not in filtered_categories:
            filtered_categories[category] = category
    return filtered_categories
