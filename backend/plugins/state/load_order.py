"""SoAI - Plugin dependency load-order resolution [backend/plugins/state/load_order.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = ("get_plugin_load_order",)


def get_plugin_load_order(graph: dict[str, set[str]]) -> list[str]:
    path: set[str] = set()
    visited: set[str] = set()
    sorted_order: list[str] = []

    def visit(node: str) -> None:
        if node in path:
            raise ValidationError(f"Circular dependency detected involving plugin: {node}")
        if node in visited:
            return
        path.add(node)
        visited.add(node)
        for dependency_name in sorted(graph.get(node, set())):
            if dependency_name not in graph:
                raise ValidationError(
                    f"Plugin '{node}' has an unresolved dependency on a missing plugin: '{dependency_name}'.",
                )
            visit(dependency_name)
        path.remove(node)
        sorted_order.append(node)

    for node in graph:
        if node not in visited:
            visit(node)
    return sorted_order
