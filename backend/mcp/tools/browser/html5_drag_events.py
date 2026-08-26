"""SoAI - Browser HTML5 drag/drop event support [backend/mcp/tools/browser/html5_drag_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from playwright.async_api import Locator

    from core.types.json import JSONDict, JSONValue

__all__ = (
    "cleanup_drag_probe",
    "dispatch_html5_drag_fallback",
    "drag_probe_drop_count",
    "empty_drag_probe_counts",
    "install_drag_probe",
    "is_html5_draggable",
    "read_drag_probe_counts",
)

_DRAG_PROBE_INSTALL_SCRIPT = """
element => {
    const documentNode = element.ownerDocument;
    const windowObject = documentNode.defaultView;
    if (!windowObject) {
        return false;
    }
    const previous = windowObject.__soaiBrowserDragProbe;
    if (previous && typeof previous.cleanup === "function") {
        previous.cleanup();
    }
    const counts = { dragstart: 0, dragover: 0, drop: 0, dragend: 0 };
    const handler = event => {
        if (Object.prototype.hasOwnProperty.call(counts, event.type)) {
            counts[event.type] += 1;
        }
    };
    const eventTypes = Object.keys(counts);
    for (const eventType of eventTypes) {
        documentNode.addEventListener(eventType, handler, true);
    }
    windowObject.__soaiBrowserDragProbe = {
        counts,
        cleanup: () => {
            for (const eventType of eventTypes) {
                documentNode.removeEventListener(eventType, handler, true);
            }
        },
    };
    return true;
}
"""

_DRAG_PROBE_READ_SCRIPT = """
element => {
    const windowObject = element.ownerDocument.defaultView;
    const probe = windowObject ? windowObject.__soaiBrowserDragProbe : null;
    if (!probe || !probe.counts) {
        return null;
    }
    return {
        dragstart: probe.counts.dragstart || 0,
        dragover: probe.counts.dragover || 0,
        drop: probe.counts.drop || 0,
        dragend: probe.counts.dragend || 0,
    };
}
"""

_DRAG_PROBE_CLEANUP_SCRIPT = """
element => {
    const windowObject = element.ownerDocument.defaultView;
    const probe = windowObject ? windowObject.__soaiBrowserDragProbe : null;
    if (probe && typeof probe.cleanup === "function") {
        probe.cleanup();
    }
    if (windowObject) {
        delete windowObject.__soaiBrowserDragProbe;
    }
    return true;
}
"""

_DRAG_SOURCE_DRAGGABLE_SCRIPT = """
element => element instanceof HTMLElement && element.draggable === true
"""

_MARK_DRAG_SOURCE_SCRIPT = """
(element, marker) => {
    element.setAttribute("data-soai-browser-drag-source", marker);
    return true;
}
"""

_MARK_DRAG_TARGET_SCRIPT = """
(element, marker) => {
    element.setAttribute("data-soai-browser-drag-target", marker);
    return true;
}
"""

_CLEANUP_DRAG_SOURCE_MARKER_SCRIPT = """
element => {
    element.removeAttribute("data-soai-browser-drag-source");
    return true;
}
"""

_CLEANUP_DRAG_TARGET_MARKER_SCRIPT = """
element => {
    element.removeAttribute("data-soai-browser-drag-target");
    return true;
}
"""

_HTML5_DRAG_FALLBACK_SCRIPT = """
(_element, marker) => {
    const source = document.querySelector(`[data-soai-browser-drag-source="${marker}"]`);
    const target = document.querySelector(`[data-soai-browser-drag-target="${marker}"]`);
    if (!source || !target || typeof DataTransfer !== "function" || typeof DragEvent !== "function") {
        return false;
    }
    const dataTransfer = new DataTransfer();
    const options = { bubbles: true, cancelable: true, dataTransfer };
    source.dispatchEvent(new DragEvent("dragstart", options));
    target.dispatchEvent(new DragEvent("dragenter", options));
    target.dispatchEvent(new DragEvent("dragover", options));
    target.dispatchEvent(new DragEvent("drop", options));
    source.dispatchEvent(new DragEvent("dragend", options));
    return true;
}
"""


def empty_drag_probe_counts() -> JSONDict:
    return {"dragstart": 0, "dragover": 0, "drop": 0, "dragend": 0}


def _normalize_drag_probe_counts(value: JSONValue) -> JSONDict:
    if not isinstance(value, dict):
        return empty_drag_probe_counts()
    counts = empty_drag_probe_counts()
    for key in counts:
        raw_count = value.get(key)
        counts[key] = raw_count if is_strict_int(raw_count) and raw_count >= 0 else 0
    return counts


def drag_probe_drop_count(counts: JSONDict) -> int:
    value = counts.get("drop")
    if is_strict_int(value) and value >= 0:
        return value
    return 0


async def install_drag_probe(locator: Locator) -> None:
    await locator.evaluate(_DRAG_PROBE_INSTALL_SCRIPT)


async def read_drag_probe_counts(locator: Locator) -> JSONDict:
    return _normalize_drag_probe_counts(await locator.evaluate(_DRAG_PROBE_READ_SCRIPT))


async def cleanup_drag_probe(locator: Locator) -> None:
    await locator.evaluate(_DRAG_PROBE_CLEANUP_SCRIPT)


async def is_html5_draggable(locator: Locator) -> bool:
    return bool(await locator.evaluate(_DRAG_SOURCE_DRAGGABLE_SCRIPT))


async def dispatch_html5_drag_fallback(
    from_locator: Locator,
    to_locator: Locator,
) -> bool:
    marker = uuid.uuid4().hex
    await from_locator.evaluate(_MARK_DRAG_SOURCE_SCRIPT, marker)
    await to_locator.evaluate(_MARK_DRAG_TARGET_SCRIPT, marker)
    try:
        return bool(await to_locator.evaluate(_HTML5_DRAG_FALLBACK_SCRIPT, marker))
    finally:
        await from_locator.evaluate(_CLEANUP_DRAG_SOURCE_MARKER_SCRIPT)
        await to_locator.evaluate(_CLEANUP_DRAG_TARGET_MARKER_SCRIPT)
