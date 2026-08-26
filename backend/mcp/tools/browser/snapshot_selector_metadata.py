"""SoAI - Browser snapshot selector metadata capture [backend/mcp/tools/browser/snapshot_selector_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from playwright.async_api import Frame

    from core.types.json import JSONValue

__all__ = (
    "SnapshotSelectorOverride",
    "SnapshotSupplementalRef",
    "collect_snapshot_selector_metadata",
)

_SNAPSHOT_SELECTOR_METADATA_SCRIPT = """
    () => {
        const normalizeText = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
        const escapeCss = (value) => {
            if (globalThis.CSS && typeof globalThis.CSS.escape === 'function') {
                return globalThis.CSS.escape(value);
            }
            return String(value).replace(/[^a-zA-Z0-9_-]/g, '\\\\$&');
        };
        const buildSelector = (element) => {
            const segments = [];
            let current = element;
            while (current && current.nodeType === Node.ELEMENT_NODE && current !== document.body) {
                const tag = String(current.tagName || '').toLowerCase();
                if (!tag) {
                    return null;
                }
                const elementId = normalizeText(current.getAttribute('id'));
                if (elementId && document.getElementById(elementId) === current) {
                    segments.unshift(`#${escapeCss(elementId)}`);
                    return segments.join(' > ');
                }
                let nth = 1;
                let sibling = current.previousElementSibling;
                while (sibling) {
                    if (String(sibling.tagName || '').toLowerCase() === tag) {
                        nth += 1;
                    }
                    sibling = sibling.previousElementSibling;
                }
                segments.unshift(`${tag}:nth-of-type(${nth})`);
                current = current.parentElement;
            }
            segments.unshift('body');
            return segments.join(' > ');
        };
        const isVisible = (element) => {
            const style = globalThis.getComputedStyle(element);
            if (!style || style.display === 'none' || style.visibility === 'hidden') {
                return false;
            }
            const rect = element.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
        };
        const labelTextFor = (element) => {
            const ariaLabel = normalizeText(element.getAttribute('aria-label'));
            if (ariaLabel) {
                return ariaLabel;
            }
            const labelledBy = normalizeText(element.getAttribute('aria-labelledby'));
            if (labelledBy) {
                const text = labelledBy
                    .split(/\\s+/)
                    .map((id) => document.getElementById(id))
                    .filter((node) => node)
                    .map((node) => normalizeText(node.textContent))
                    .filter((text) => text)
                    .join(' ');
                if (text) {
                    return text;
                }
            }
            const parentLabel = element.closest('label');
            if (parentLabel) {
                const text = normalizeText(parentLabel.textContent);
                if (text) {
                    return text;
                }
            }
            const elementId = normalizeText(element.getAttribute('id'));
            if (elementId) {
                const label = Array.from(document.querySelectorAll('label[for]')).find(
                    (candidate) => normalizeText(candidate.getAttribute('for')) === elementId
                );
                if (label) {
                    const text = normalizeText(label.textContent);
                    if (text) {
                        return text;
                    }
                }
            }
            const nameValue = normalizeText(element.getAttribute('name'));
            if (nameValue) {
                return nameValue;
            }
            if (elementId) {
                return elementId;
            }
            const titleValue = normalizeText(element.getAttribute('title'));
            if (titleValue) {
                return titleValue;
            }
            return '';
        };
        const overrides = [];
        for (const element of Array.from(document.querySelectorAll('[data-soai-temp-actionable="true"]'))) {
            if (!isVisible(element)) {
                continue;
            }
            const role = normalizeText(element.getAttribute('role')).toLowerCase() || 'button';
            const name = labelTextFor(element);
            const selector = buildSelector(element);
            if (!name || !selector) {
                continue;
            }
            overrides.push({ role, name, selector });
        }
        const supplemental = [];
        let selectIndex = 1;
        for (const element of Array.from(document.querySelectorAll('select'))) {
            if (!isVisible(element) || element.disabled) {
                continue;
            }
            const selector = buildSelector(element);
            if (!selector) {
                continue;
            }
            const derivedName = labelTextFor(element) || `Select ${selectIndex}`;
            selectIndex += 1;
            supplemental.push({
                role: 'combobox',
                name: derivedName,
                selector,
                rendered_line: `- combobox "${derivedName}":`,
            });
        }
        return { overrides, supplemental };
    }
"""


@dataclass(frozen=True, slots=True)
class SnapshotSelectorOverride:
    role: str
    name: str
    selector: str


@dataclass(frozen=True, slots=True)
class SnapshotSupplementalRef:
    role: str
    name: str
    selector: str
    rendered_line: str


def _read_text_field(item: dict[str, JSONValue], key: str) -> str | None:
    raw_value = item.get(key)
    if not isinstance(raw_value, str):
        return None
    normalized = raw_value.strip()
    return normalized or None


def _collect_override_items(raw_items: JSONValue) -> tuple[SnapshotSelectorOverride, ...]:
    if not isinstance(raw_items, list):
        return ()
    collected: list[SnapshotSelectorOverride] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        role = _read_text_field(raw_item, "role")
        name = _read_text_field(raw_item, "name")
        selector = _read_text_field(raw_item, "selector")
        if role is None or name is None or selector is None:
            continue
        collected.append(SnapshotSelectorOverride(role=role, name=name, selector=selector))
    return tuple(collected)


def _collect_supplemental_items(raw_items: JSONValue) -> tuple[SnapshotSupplementalRef, ...]:
    if not isinstance(raw_items, list):
        return ()
    collected: list[SnapshotSupplementalRef] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        role = _read_text_field(raw_item, "role")
        name = _read_text_field(raw_item, "name")
        selector = _read_text_field(raw_item, "selector")
        rendered_line = _read_text_field(raw_item, "rendered_line")
        if role is None or name is None or selector is None or rendered_line is None:
            continue
        collected.append(
            SnapshotSupplementalRef(
                role=role,
                name=name,
                selector=selector,
                rendered_line=rendered_line,
            ),
        )
    return tuple(collected)


async def collect_snapshot_selector_metadata(
    frame: Frame,
) -> tuple[tuple[SnapshotSelectorOverride, ...], tuple[SnapshotSupplementalRef, ...]]:
    raw_result = await frame.evaluate(_SNAPSHOT_SELECTOR_METADATA_SCRIPT)
    result = coerce_json_dict(raw_result)
    if result is None:
        return ((), ())
    return (
        _collect_override_items(result.get("overrides")),
        _collect_supplemental_items(result.get("supplemental")),
    )
