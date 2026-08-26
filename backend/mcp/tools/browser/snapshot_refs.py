"""SoAI - Stable browser snapshot ref assignment [backend/mcp/tools/browser/snapshot_refs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.browser.aria_snapshot_lines import parse_aria_snapshot_role_and_name
from mcp.tools.browser.types import SnapshotRefMapping

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.browser.snapshot_selector_metadata import (
        SnapshotSelectorOverride,
        SnapshotSupplementalRef,
    )
    from mcp.tools.browser.types import ActionableRole, BrowserSessionState, FramePath

__all__ = (
    "collect_actionable_snapshot_refs",
    "finalize_snapshot_ref_state",
    "normalize_ref_alias",
)


def is_actionable_role(role: str) -> ActionableRole | None:
    normalized = (role or "").strip().lower()
    if normalized == "button":
        return "button"
    if normalized == "link":
        return "link"
    if normalized == "textbox":
        return "textbox"
    if normalized == "searchbox":
        return "searchbox"
    if normalized == "checkbox":
        return "checkbox"
    if normalized == "radio":
        return "radio"
    if normalized == "combobox":
        return "combobox"
    if normalized == "option":
        return "option"
    if normalized == "tab":
        return "tab"
    if normalized == "menuitem":
        return "menuitem"
    if normalized == "switch":
        return "switch"
    if normalized == "listitem":
        return "listitem"
    if normalized == "gridcell":
        return "gridcell"
    if normalized == "treeitem":
        return "treeitem"
    return None


def normalize_ref_alias(value: str) -> str:
    return "".join(character for character in value.strip().lower() if character.isalnum())


def _register_ref_alias(
    aliases: dict[str, str],
    conflicts: set[str],
    *,
    alias: str,
    ref: str,
) -> None:
    normalized = normalize_ref_alias(alias)
    if not normalized or normalized == ref or normalized in conflicts:
        return
    existing_ref = aliases.get(normalized)
    if existing_ref is None:
        aliases[normalized] = ref
        return
    if existing_ref != ref:
        aliases.pop(normalized, None)
        conflicts.add(normalized)


def finalize_snapshot_ref_state(
    state: BrowserSessionState,
    *,
    active_refs: dict[str, SnapshotRefMapping],
    ref_aliases: dict[str, str],
) -> None:
    state.refs.clear()
    state.refs.update(active_refs)
    state.ref_aliases.clear()
    state.ref_aliases.update(ref_aliases)
    state.ref_registry = {mapping: ref for ref, mapping in active_refs.items()}


def _build_ref_aliases(role: ActionableRole, name: str) -> tuple[str, ...]:
    aliases = [role, name, f"{role} {name}"]
    if role == "searchbox":
        aliases.extend(["search", "searchbox"])
    if role == "listitem":
        aliases.extend(["item", "list item"])
    if role == "gridcell":
        aliases.extend(["cell", "grid cell"])
    if role == "treeitem":
        aliases.extend(["node", "tree item"])
    return tuple(aliases)


def _resolve_ref_for_mapping(state: BrowserSessionState, mapping: SnapshotRefMapping) -> str:
    existing = state.ref_registry.get(mapping)
    if isinstance(existing, str) and existing.strip():
        return existing
    ref = f"e{state.next_ref_index}"
    state.next_ref_index += 1
    state.ref_registry[mapping] = ref
    return ref


def collect_actionable_snapshot_refs(
    snapshot_text: str,
    state: BrowserSessionState,
    *,
    frame_path: FramePath,
    max_refs: int,
    selector_overrides: tuple[SnapshotSelectorOverride, ...] = (),
    supplemental_refs: tuple[SnapshotSupplementalRef, ...] = (),
) -> tuple[str, list[JSONDict], dict[str, SnapshotRefMapping], dict[str, str], set[str]]:
    refs: list[JSONDict] = []
    role_name_counts: dict[tuple[ActionableRole, str], int] = {}
    ref_aliases: dict[str, str] = {}
    ref_alias_conflicts: set[str] = set()
    rendered_lines: list[str] = []
    active_refs: dict[str, SnapshotRefMapping] = {}
    selector_override_counts: dict[tuple[ActionableRole, str], int] = {}
    selector_lookup: dict[tuple[ActionableRole, str, int], str] = {}
    for override in selector_overrides:
        role = is_actionable_role(override.role)
        if role is None:
            continue
        name = override.name.strip()
        if not name:
            continue
        key = (role, name)
        nth = selector_override_counts.get(key, 0)
        selector_override_counts[key] = nth + 1
        selector_lookup[(role, name, nth)] = override.selector
    for line in snapshot_text.splitlines():
        rendered_line = line
        parsed = parse_aria_snapshot_role_and_name(line)
        if parsed is None:
            rendered_lines.append(rendered_line)
            continue
        role_raw, name_raw = parsed
        role = is_actionable_role(role_raw)
        if role is None:
            rendered_lines.append(rendered_line)
            continue
        name = name_raw.strip()
        if not name:
            rendered_lines.append(rendered_line)
            continue
        if len(refs) >= max_refs:
            rendered_lines.append(rendered_line)
            continue
        key = (role, name)
        nth = role_name_counts.get(key, 0)
        role_name_counts[key] = nth + 1
        mapping = SnapshotRefMapping(
            role=role,
            name=name,
            nth=nth,
            frame_path=frame_path,
            selector=selector_lookup.get((role, name, nth)),
        )
        ref = _resolve_ref_for_mapping(state, mapping)
        active_refs[ref] = mapping
        for alias in _build_ref_aliases(role, name):
            _register_ref_alias(ref_aliases, ref_alias_conflicts, alias=alias, ref=ref)
        refs.append({"ref": ref, "role": role, "name": name})
        rendered_lines.append(f"{line} [ref={ref}]")
    for supplemental in supplemental_refs:
        if len(refs) >= max_refs:
            break
        role = is_actionable_role(supplemental.role)
        if role is None:
            continue
        name = supplemental.name.strip()
        if not name:
            continue
        key = (role, name)
        nth = role_name_counts.get(key, 0)
        role_name_counts[key] = nth + 1
        mapping = SnapshotRefMapping(
            role=role,
            name=name,
            nth=nth,
            frame_path=frame_path,
            selector=supplemental.selector,
        )
        ref = _resolve_ref_for_mapping(state, mapping)
        active_refs[ref] = mapping
        for alias in _build_ref_aliases(role, name):
            _register_ref_alias(ref_aliases, ref_alias_conflicts, alias=alias, ref=ref)
        refs.append({"ref": ref, "role": role, "name": name})
        rendered_lines.append(f"{supplemental.rendered_line} [ref={ref}]")
    return ("\n".join(rendered_lines), refs, active_refs, ref_aliases, ref_alias_conflicts)
