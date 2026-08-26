"""SoAI - Browser frame tree helpers [backend/mcp/tools/browser/frame_tree.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Frame, Page

    from mcp.tools.browser.types import FramePath, SnapshotFrameTreeSignature

__all__ = (
    "build_frame_tree_signature",
    "collect_page_frames",
    "format_frame_label",
    "resolve_frame_by_path",
)


def _walk_frame(frame: Frame, *, frame_path: FramePath) -> list[tuple[FramePath, Frame]]:
    items: list[tuple[FramePath, Frame]] = [(frame_path, frame)]
    for child_index, child_frame in enumerate(frame.child_frames):
        items.extend(_walk_frame(child_frame, frame_path=frame_path + (child_index,)))
    return items


def collect_page_frames(page: Page) -> list[tuple[FramePath, Frame]]:
    return _walk_frame(page.main_frame, frame_path=())


def build_frame_tree_signature(page: Page) -> SnapshotFrameTreeSignature:
    items: list[tuple[FramePath, str, str]] = []
    for frame_path, frame in collect_page_frames(page):
        items.append((frame_path, str(frame.name or ""), str(frame.url or "")))
    return tuple(items)


def format_frame_label(frame: Frame, *, frame_path: FramePath) -> str:
    if not frame_path:
        return "main"
    path_label = ".".join(str(index + 1) for index in frame_path)
    frame_name = str(frame.name or "").strip()
    if frame_name:
        return f"{path_label}: {frame_name}"
    frame_url = str(frame.url or "").strip()
    if frame_url:
        return f"{path_label}: {frame_url}"
    return path_label


def resolve_frame_by_path(page: Page, frame_path: FramePath) -> Frame | None:
    frame = page.main_frame
    for child_index in frame_path:
        child_frames = list(frame.child_frames)
        if child_index < 0 or child_index >= len(child_frames):
            return None
        frame = child_frames[child_index]
    return frame
