"""SoAI - Browser snapshot capture helpers [backend/mcp/tools/browser/snapshot_capture.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from playwright.async_api import Error

from core.errors.exception_logging import log_handled_exception
from core.logging.trace import get_logger
from mcp.tools.browser.aria_snapshot_lines import filter_snapshot_refs_by_roles
from mcp.tools.browser.frame_tree import (
    build_frame_tree_signature,
    collect_page_frames,
    format_frame_label,
)
from mcp.tools.browser.playwright_error_classification import is_transient_snapshot_error
from mcp.tools.browser.snapshot_accessibility import (
    MainFrameSnapshotTransientError,
    capture_accessibility_snapshot_text,
)
from mcp.tools.browser.snapshot_capture_config import (
    parse_snapshot_roles,
    resolve_snapshot_max_chars,
    resolve_snapshot_max_refs,
)
from mcp.tools.browser.snapshot_output import (
    filter_snapshot_output_text,
    merge_snapshot_alias_maps,
)
from mcp.tools.browser.snapshot_prepare_scripts import (
    SNAPSHOT_PREPARE_SCRIPT,
    SNAPSHOT_RESTORE_SCRIPT,
)
from mcp.tools.browser.snapshot_refs import (
    collect_actionable_snapshot_refs,
    finalize_snapshot_ref_state,
)
from mcp.tools.browser.snapshot_selector_metadata import (
    collect_snapshot_selector_metadata,
)
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from playwright.async_api import Page

    from core.types.json import JSONDict
    from mcp.tools.browser.snapshot_selector_metadata import (
        SnapshotSelectorOverride,
        SnapshotSupplementalRef,
    )
    from mcp.tools.browser.types import (
        BrowserSessionState,
        SnapshotFrameTreeSignature,
        SnapshotRefMapping,
    )
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "capture_page_snapshot_with_timeout",
    "parse_snapshot_roles",
    "resolve_snapshot_max_chars",
    "resolve_snapshot_max_refs",
)

LOGGER_NAME = "SoAI.mcp.tools.snapshot_capture"
OPERATION_WAIT_FOR_LOAD_STATE = "mcp.tools.browser.snapshot_capture.wait_for_load_state"


async def capture_page_snapshot(
    *,
    state: BrowserSessionState,
    page: Page,
    frame_tree_signature: SnapshotFrameTreeSignature,
    action_timeout_sec: float,
    max_refs: int,
    roles: tuple[str, ...] | None,
) -> tuple[str, list[JSONDict]]:
    rendered_sections_full: list[str] = []
    rendered_sections_output: list[str] = []
    refs_output: list[JSONDict] = []
    active_refs: dict[str, SnapshotRefMapping] = {}
    ref_aliases: dict[str, str] = {}
    ref_alias_conflicts: set[str] = set()
    allowed_roles: set[str] = set(roles) if roles is not None else set()

    frame_items = collect_page_frames(page)
    for frame_path, frame in frame_items:
        prep_result: JSONDict = {"possible_consent_banner": False}
        prep_failed = False
        metadata_failed = False
        try:
            prep_result = await frame.evaluate(SNAPSHOT_PREPARE_SCRIPT)
        except Error:
            prep_failed = True
        locator = frame.locator("body")
        raw_text: str | None = None
        selector_overrides: tuple[SnapshotSelectorOverride, ...] = ()
        supplemental_refs: tuple[SnapshotSupplementalRef, ...] = ()
        restore_failed = False
        try:
            raw_text = await locator.aria_snapshot(timeout=int(action_timeout_sec) * 1000)
            try:
                selector_overrides, supplemental_refs = await collect_snapshot_selector_metadata(
                    frame,
                )
            except Error:
                metadata_failed = True
        except Error as exception:
            if is_transient_snapshot_error(exception):
                if not frame_path:
                    raise MainFrameSnapshotTransientError(str(exception)) from exception
                continue
            if not frame_path:
                raw_text = await capture_accessibility_snapshot_text(
                    page,
                    action_timeout_sec=action_timeout_sec,
                )
                if raw_text is None:
                    rendered_sections_full.append(
                        "(snapshot unavailable: browser accessibility snapshot failed)",
                    )
                    continue
                try:
                    selector_overrides, supplemental_refs = (
                        await collect_snapshot_selector_metadata(frame)
                    )
                except Error:
                    metadata_failed = True
            else:
                rendered_sections_full.append(
                    f"--- Frame {format_frame_label(frame, frame_path=frame_path)} ---",
                )
                if prep_failed:
                    rendered_sections_full.append(
                        "(snapshot note: browser preparation failed)",
                    )
                rendered_sections_full.append(
                    "(snapshot unavailable: browser accessibility snapshot failed)",
                )
                continue
        finally:
            try:
                await frame.evaluate(SNAPSHOT_RESTORE_SCRIPT)
            except Error:
                restore_failed = True
        if not isinstance(raw_text, str) or not raw_text.strip():
            if not frame_path:
                raw_text = await capture_accessibility_snapshot_text(
                    page,
                    action_timeout_sec=action_timeout_sec,
                )
                if raw_text is None:
                    rendered_sections_full.append("(snapshot unavailable: empty aria snapshot)")
                    continue
            else:
                continue
        remaining_refs = max(0, max_refs - len(active_refs))
        snapshot_lines: set[str] = set(raw_text.splitlines())
        res = collect_actionable_snapshot_refs(
            raw_text,
            state,
            frame_path=frame_path,
            max_refs=remaining_refs,
            selector_overrides=selector_overrides,
            supplemental_refs=tuple(
                item for item in supplemental_refs if item.rendered_line not in snapshot_lines
            ),
        )
        (
            rendered_text_full,
            frame_refs_full,
            frame_active_refs,
            frame_aliases,
            frame_alias_conflicts,
        ) = res
        if frame_path:
            rendered_sections_full.append(
                f"--- Frame {format_frame_label(frame, frame_path=frame_path)} ---",
            )
        if prep_failed:
            rendered_sections_full.append(
                "(snapshot note: browser preparation failed)",
            )
        if restore_failed:
            rendered_sections_full.append(
                "(snapshot note: browser restoration failed)",
            )
        if metadata_failed:
            rendered_sections_full.append(
                "(snapshot note: browser selector metadata failed)",
            )
        if prep_result.get("possible_consent_banner"):
            rendered_sections_full.append(
                "(Note: A potential consent banner was detected in this frame.)",
            )
        rendered_sections_full.append(rendered_text_full)
        active_refs.update(frame_active_refs)
        output_text = rendered_text_full
        output_refs: list[JSONDict] = frame_refs_full
        if roles is not None:
            output_text = filter_snapshot_output_text(
                rendered_text_full,
                allowed_roles=allowed_roles,
            )
            output_refs = [
                item
                for item in filter_snapshot_refs_by_roles(
                    frame_refs_full,
                    allowed_roles=allowed_roles,
                )
                if isinstance(item, dict)
            ]
        if output_text.strip():
            if frame_path:
                rendered_sections_output.append(
                    f"--- Frame {format_frame_label(frame, frame_path=frame_path)} ---",
                )
            rendered_sections_output.append(output_text)
            refs_output.extend(output_refs)
        merge_snapshot_alias_maps(
            ref_aliases,
            ref_alias_conflicts,
            frame_aliases,
            frame_alias_conflicts,
        )

    full_snapshot_text = "\n\n".join(
        section for section in rendered_sections_full if section.strip()
    )
    output_snapshot_text = "\n\n".join(
        section for section in rendered_sections_output if section.strip()
    )
    finalize_snapshot_ref_state(
        state,
        active_refs=active_refs,
        ref_aliases=ref_aliases,
    )
    state.ref_page_url, state.ref_frame_tree_signature, state.last_snapshot_text = (
        page.url,
        frame_tree_signature,
        full_snapshot_text,
    )
    return (full_snapshot_text if roles is None else output_snapshot_text, refs_output)


async def capture_page_snapshot_with_timeout(
    *,
    utility_tools: MCPUtilityToolsProtocol,
    state: BrowserSessionState,
    page: Page,
    action_timeout_sec: float,
    roles: tuple[str, ...] | None,
) -> tuple[str, list[JSONDict], int]:
    max_chars, max_refs = resolve_snapshot_max_chars(utility_tools), resolve_snapshot_max_refs(
        utility_tools,
    )
    async with asyncio.timeout(float(action_timeout_sec) + 30.0):
        for attempt in range(3):
            try:
                try:
                    await page.wait_for_load_state(
                        "domcontentloaded",
                        timeout=min(2000, int(action_timeout_sec) * 1000),
                    )
                except (Error, TimeoutError) as exception:
                    log_handled_exception(
                        get_logger(LOGGER_NAME),
                        exception,
                        message="Page load wait did not complete before snapshot capture.",
                        operation=OPERATION_WAIT_FOR_LOAD_STATE,
                        level="debug",
                    )
                current_signature = build_frame_tree_signature(page)
                snapshot_text, refs = await capture_page_snapshot(
                    state=state,
                    page=page,
                    frame_tree_signature=current_signature,
                    action_timeout_sec=action_timeout_sec,
                    max_refs=max_refs,
                    roles=roles,
                )
                return (snapshot_text, refs, max_chars)
            except MainFrameSnapshotTransientError:
                if attempt < 2:
                    await asyncio.sleep(0.2 * float(attempt + 1))
                continue
        raise MCPToolError(-32603, "Frame was detached during snapshot capture.")
