"""SoAI - Per-tab browser snapshot ref state lifecycle [backend/mcp/tools/browser/page_ref_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.browser.types import PageRefState

if TYPE_CHECKING:
    from playwright.async_api import Page

    from mcp.tools.browser.types import BrowserSessionState

__all__ = (
    "capture_active_page_ref_state",
    "prune_page_ref_states",
    "reset_active_page_ref_state",
    "restore_captured_active_page_ref_state",
    "restore_active_page_ref_state",
    "transfer_active_page_ref_state",
)


def capture_active_page_ref_state(state: BrowserSessionState) -> PageRefState:
    return PageRefState(
        refs=dict(state.refs),
        ref_aliases=dict(state.ref_aliases),
        ref_registry=dict(state.ref_registry),
        next_ref_index=state.next_ref_index,
        ref_page_url=state.ref_page_url,
        ref_frame_tree_signature=state.ref_frame_tree_signature,
        last_snapshot_text=state.last_snapshot_text,
    )


def restore_captured_active_page_ref_state(
    state: BrowserSessionState,
    captured_state: PageRefState,
) -> None:
    state.refs = dict(captured_state.refs)
    state.ref_aliases = dict(captured_state.ref_aliases)
    state.ref_registry = dict(captured_state.ref_registry)
    state.next_ref_index = captured_state.next_ref_index
    state.ref_page_url = captured_state.ref_page_url
    state.ref_frame_tree_signature = captured_state.ref_frame_tree_signature
    state.last_snapshot_text = captured_state.last_snapshot_text


def _park_active_ref_state(state: BrowserSessionState, page: Page) -> None:
    state.page_ref_states[id(page)] = PageRefState(
        refs=state.refs,
        ref_aliases=state.ref_aliases,
        ref_registry=state.ref_registry,
        next_ref_index=state.next_ref_index,
        ref_page_url=state.ref_page_url,
        ref_frame_tree_signature=state.ref_frame_tree_signature,
        last_snapshot_text=state.last_snapshot_text,
    )


def _install_active_ref_state(state: BrowserSessionState, page: Page, *, reload: bool) -> None:
    stale = state.page_ref_states.pop(id(page), None)
    if reload or stale is None:
        reset_active_page_ref_state(state)
        return
    state.refs = stale.refs
    state.ref_aliases = stale.ref_aliases
    state.ref_registry = stale.ref_registry
    state.next_ref_index = stale.next_ref_index
    state.ref_page_url = stale.ref_page_url
    state.ref_frame_tree_signature = stale.ref_frame_tree_signature
    state.last_snapshot_text = stale.last_snapshot_text


def transfer_active_page_ref_state(
    state: BrowserSessionState,
    *,
    outgoing_page: Page,
    incoming_page: Page,
    reload_incoming: bool,
) -> None:
    if outgoing_page is incoming_page:
        return
    _park_active_ref_state(state, outgoing_page)
    _install_active_ref_state(state, incoming_page, reload=reload_incoming)


def restore_active_page_ref_state(
    state: BrowserSessionState,
    *,
    incoming_page: Page,
) -> None:
    _install_active_ref_state(state, incoming_page, reload=False)


def reset_active_page_ref_state(state: BrowserSessionState) -> None:
    state.refs = {}
    state.ref_aliases = {}
    state.ref_registry = {}
    state.next_ref_index = 1
    state.ref_page_url = None
    state.ref_frame_tree_signature = ()
    state.last_snapshot_text = None


def prune_page_ref_states(state: BrowserSessionState, live_page_ids: set[int]) -> None:
    for page_id in [pid for pid in state.page_ref_states if pid not in live_page_ids]:
        del state.page_ref_states[page_id]
