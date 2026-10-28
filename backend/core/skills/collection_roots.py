"""SoAI - Repository skill root authority and package membership [backend/core/skills/collection_roots.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import posixpath
from collections.abc import Container

from core.archives.constants import validate_member_name
from core.archives.zip_plan import ValidatedZipMember
from core.errors.exceptions import ValidationError
from core.types.json import JSONDict, JSONValue, is_str_list

__all__ = (
    "SKILL_PLUGIN_MANIFEST_PATHS",
    "resolve_collection_skill_roots",
    "group_skill_members",
    "collection_plugin_manifest_paths",
    "collection_skill_source_binding",
)

SKILL_PLUGIN_MANIFEST_PATHS = (
    ".claude-plugin/plugin.json",
    ".codex-plugin/plugin.json",
    "plugin.json",
    ".claude-plugin/marketplace.json",
)
_CONVENTIONAL_ROOTS = ("skills", ".agents/skills", ".claude/skills", ".codex/skills")


def _declaration_base(path: str) -> str:
    for suffix in SKILL_PLUGIN_MANIFEST_PATHS:
        if path == suffix:
            return ""
        if path.endswith(f"/{suffix}"):
            return path[: -len(suffix) - 1]
    raise ValidationError("Unsupported skill plugin manifest location.")


def _marketplace_plugins(payload: JSONDict) -> tuple[tuple[str, JSONDict], ...]:
    plugins = payload.get("plugins", [])
    if not isinstance(plugins, list):
        raise ValidationError("Skill marketplace plugins must be an array.")
    output: list[tuple[str, JSONDict]] = []
    for plugin in plugins:
        if not isinstance(plugin, dict):
            raise ValidationError("Skill marketplace entries must be objects.")
        source = plugin.get("source", "./")
        if isinstance(source, str):
            output.extend((path, plugin) for path in _declared_paths(source))
    return tuple(output)


def collection_plugin_manifest_paths(declarations: dict[str, JSONDict]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                posixpath.join(source, suffix)
                for path, payload in declarations.items()
                if path.endswith("marketplace.json")
                for source, _plugin in _marketplace_plugins(payload)
                for suffix in SKILL_PLUGIN_MANIFEST_PATHS
                if not suffix.endswith("marketplace.json")
            }
        )
    )


def collection_skill_source_binding(
    root: str, declarations: dict[str, JSONDict]
) -> tuple[str, tuple[JSONDict, ...]]:
    owners: list[tuple[str, JSONDict]] = []
    for path, payload in declarations.items():
        if path.endswith("marketplace.json"):
            owners.extend(_marketplace_plugins(payload))
        else:
            owners.append((_declaration_base(path), payload))
    matching = [
        (base, payload)
        for base, payload in owners
        if not base or root == base or root.startswith(f"{base}/")
    ]
    depth = max((len(base) for base, _payload in matching), default=-1)
    closest = tuple((base, payload) for base, payload in matching if len(base) == depth)
    return (closest[0][0] if closest else "", tuple(payload for _base, payload in closest))


def resolve_collection_skill_roots(
    members: dict[str, ValidatedZipMember], declarations: dict[str, JSONDict]
) -> tuple[str, ...]:
    directories = {""}
    for path, member in members.items():
        parts = path.split("/")
        directories.update("/".join(parts[:index]) for index in range(1, len(parts)))
        if member.is_directory:
            directories.add(path)
    declared: set[str] = set()
    for declaration_path, payload in declarations.items():
        if declaration_path.endswith("marketplace.json"):
            for source, plugin in _marketplace_plugins(payload):
                paths = _declared_paths(plugin.get("skills"))
                declared.update(posixpath.join(source, path).rstrip("/") for path in paths)
                if source and not paths and f"{source}/skills" in directories:
                    declared.add(f"{source}/skills")
        else:
            base = _declaration_base(declaration_path)
            declared.update(
                posixpath.join(base, path).rstrip("/")
                for path in _declared_paths(payload.get("skills"))
            )
    for root in declared:
        if root not in directories:
            raise ValidationError(f"Declared skill root is missing or is not a directory: {root}")
    if declared:
        roots = set(declared)
        for conventional in _CONVENTIONAL_ROOTS:
            if any(
                root == conventional or root.startswith(f"{conventional}/") for root in declared
            ):
                roots.add(conventional)
    else:
        if "SKILL.md" in members:
            return ("",)
        roots = {root for root in _CONVENTIONAL_ROOTS if root in directories}
    discovered = {
        path.rpartition("/")[0]
        for path, member in members.items()
        if not member.is_directory
        and path.rsplit("/", 1)[-1] == "SKILL.md"
        and _containing_root(path.rpartition("/")[0], roots) is not None
    }
    if not discovered:
        raise ValidationError(
            "No SKILL.md was found in the declared or conventional skill directories."
        )
    return tuple(sorted(discovered))


def _declared_paths(value: JSONValue) -> tuple[str, ...]:
    if value is None:
        return ()
    values = [value] if isinstance(value, str) else value
    if not is_str_list(values):
        raise ValidationError("Plugin skills must declare a path or an array of paths.")
    roots: list[str] = []
    for declared_path in values:
        relative_path = declared_path[2:] if declared_path.startswith("./") else declared_path
        path = relative_path.rstrip("/")
        if path in ("", "."):
            roots.append("")
            continue
        validate_member_name(path)
        if "\\" in path or posixpath.normpath(path) != path:
            raise ValidationError("Declared skill roots must use normalized relative paths.")
        roots.append(path)
    return tuple(roots)


def group_skill_members(
    members: dict[str, ValidatedZipMember], roots: tuple[str, ...]
) -> dict[str, tuple[tuple[str, ValidatedZipMember], ...]]:
    grouped: dict[str, list[tuple[str, ValidatedZipMember]]] = {root: [] for root in roots}
    for path, member in members.items():
        ancestor = path if member.is_directory else path.rpartition("/")[0]
        containing_root = _containing_root(ancestor, grouped)
        if containing_root is not None and path != containing_root:
            grouped[containing_root].append((path, member))
    return {root: tuple(entries) for root, entries in grouped.items()}


def _containing_root(ancestor: str, roots: Container[str]) -> str | None:
    while ancestor not in roots and ancestor:
        ancestor = ancestor.rpartition("/")[0]
    return ancestor if ancestor in roots else None
