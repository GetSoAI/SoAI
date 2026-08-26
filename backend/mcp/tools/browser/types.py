"""SoAI - Browser tool types [backend/mcp/tools/browser/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.browser_adblock.protocols import EasyListAdblockServiceProtocol

if TYPE_CHECKING:
    from typing import Literal

    from filelock import BaseFileLock
    from playwright.async_api import (
        BrowserContext,
        Dialog,
        Download,
        HttpCredentials,
        Page,
    )

    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )

    type ActionableRole = Literal[
        "button",
        "link",
        "textbox",
        "searchbox",
        "checkbox",
        "radio",
        "combobox",
        "option",
        "tab",
        "menuitem",
        "switch",
        "listitem",
        "gridcell",
        "treeitem",
    ]

    type FramePath = tuple[int, ...]
    type SnapshotFrameTreeSignature = tuple[tuple[FramePath, str, str], ...]

__all__ = (
    "BrowserConsoleMessage",
    "BrowserDialogDescriptor",
    "BrowserDownload",
    "BrowserNetworkQueuedResponse",
    "BrowserNetworkRequest",
    "BrowserSessionState",
    "PageRefState",
    "PendingBrowserDownload",
    "SnapshotRefMapping",
)


@dataclass(frozen=True, slots=True)
class BrowserConsoleMessage:
    type: str
    text: str
    url: str | None = None
    line: int | None = None
    column: int | None = None


@dataclass(frozen=True, slots=True)
class BrowserNetworkRequest:
    url: str
    method: str
    status: int | None
    resource_type: str
    body: str | None
    body_truncated: bool | None
    is_main_frame_document: bool | None = None
    failure_text: str | None = None


@dataclass(frozen=True, slots=True)
class BrowserNetworkQueuedResponse:
    body_bytes: bytes | None
    url: str
    method: str
    status: int | None
    resource_type: str
    is_main_frame_document: bool | None = None
    failure_text: str | None = None


@dataclass(frozen=True, slots=True)
class SnapshotRefMapping:
    role: ActionableRole
    name: str
    nth: int
    frame_path: tuple[int, ...]
    selector: str | None = None


@dataclass(frozen=True, slots=True)
class PageRefState:
    refs: dict[str, SnapshotRefMapping]
    ref_aliases: dict[str, str]
    ref_registry: dict[SnapshotRefMapping, str]
    next_ref_index: int
    ref_page_url: str | None
    ref_frame_tree_signature: SnapshotFrameTreeSignature
    last_snapshot_text: str | None


@dataclass(frozen=True, slots=True)
class BrowserDialogDescriptor:
    dialog_id: str
    type: str
    message: str
    default_value: str


@dataclass(frozen=True, slots=True)
class BrowserDownload:
    download_id: str
    url: str
    suggested_filename: str
    file_path: str | None
    status: str
    error: str | None
    timestamp: float


@dataclass(frozen=True, slots=True)
class PendingBrowserDownload:
    download: Download
    timestamp: float
    expected_size_bytes: int | None


class BrowserSessionState:
    __slots__ = (
        "action_lock",
        "active_index",
        "adblock_service",
        "cancellation_binder",
        "console_last_call_index",
        "console_messages",
        "console_page_load_index",
        "console_queue",
        "context",
        "context_closed",
        "dialog_objects",
        "dialog_queue",
        "dialogs",
        "download_queue",
        "download_size_hints",
        "download_target_paths",
        "download_tasks",
        "downloads",
        "downloads_dir",
        "driver_connected",
        "driver_disconnect_reason",
        "finalizer_tracker",
        "host_block_cache",
        "http_credentials",
        "ignore_https_errors",
        "known_page_ids",
        "last_snapshot_text",
        "last_touched_monotonic",
        "lock",
        "network_last_call_index",
        "network_page_load_index",
        "network_queue",
        "network_requests",
        "next_dialog_id",
        "next_download_id",
        "next_ref_index",
        "owner_base",
        "owner_key",
        "page_close_queue",
        "page_open_queue",
        "page_ref_states",
        "pages",
        "persistence_mode",
        "profile",
        "profile_lock",
        "ref_aliases",
        "ref_frame_tree_signature",
        "ref_page_url",
        "ref_registry",
        "refs",
        "runtime_flags",
        "session_scope",
        "storage_manager",
        "storage_state_dirty",
        "storage_state_last_error",
        "storage_state_last_saved_monotonic",
        "storage_state_path",
        "user_data_dir",
    )

    def __init__(
        self,
        owner_key: str,
        owner_base: str,
        context: BrowserContext,
        storage_manager: StorageManagerProtocol,
        runtime_flags: RuntimeFlagsViewProtocol,
        cancellation_binder: TaskCancellationBinderProtocol | None = None,
        finalizer_tracker: TaskFinalizerTrackerProtocol | None = None,
        http_credentials: HttpCredentials | None = None,
        ignore_https_errors: bool = False,
        persistence_mode: str = "storage_state",
        user_data_dir: str | None = None,
        profile_lock: BaseFileLock | None = None,
        active_index: int = 0,
        profile: str = "default",
        session_scope: str = "conversation",
        storage_state_path: str | None = None,
        storage_state_dirty: bool = False,
        storage_state_last_saved_monotonic: float = 0.0,
        storage_state_last_error: str | None = None,
        driver_connected: bool = True,
        driver_disconnect_reason: str | None = None,
        downloads_dir: str | None = None,
        next_ref_index: int = 1,
        ref_page_url: str | None = None,
        ref_frame_tree_signature: SnapshotFrameTreeSignature = (),
        last_snapshot_text: str | None = None,
        next_dialog_id: int = 1,
        next_download_id: int = 1,
        console_last_call_index: int = 0,
        console_page_load_index: int = 0,
        network_last_call_index: int = 0,
        network_page_load_index: int = 0,
        adblock_service: EasyListAdblockServiceProtocol | None = None,
    ) -> None:
        self.owner_key = owner_key
        self.owner_base = owner_base
        self.context = context
        self.http_credentials = http_credentials
        self.ignore_https_errors = bool(ignore_https_errors)
        self.persistence_mode = persistence_mode
        self.user_data_dir = user_data_dir
        self.profile_lock = profile_lock
        self.storage_manager = storage_manager
        self.runtime_flags = runtime_flags
        self.cancellation_binder = cancellation_binder
        self.finalizer_tracker = finalizer_tracker
        self.lock = asyncio.Lock()
        self.action_lock = asyncio.Lock()
        self.pages: list[Page] = []
        self.active_index = active_index
        self.profile = profile
        self.session_scope = session_scope
        self.storage_state_path = storage_state_path
        self.storage_state_dirty = storage_state_dirty
        self.storage_state_last_saved_monotonic = storage_state_last_saved_monotonic
        self.storage_state_last_error = storage_state_last_error
        self.driver_connected = bool(driver_connected)
        self.driver_disconnect_reason = driver_disconnect_reason
        self.refs: dict[str, SnapshotRefMapping] = {}
        self.ref_aliases: dict[str, str] = {}
        self.ref_registry: dict[SnapshotRefMapping, str] = {}
        self.next_ref_index = next_ref_index
        self.ref_page_url = ref_page_url
        self.ref_frame_tree_signature = ref_frame_tree_signature
        self.last_snapshot_text = last_snapshot_text
        self.dialog_queue: asyncio.Queue[tuple[BrowserDialogDescriptor, Dialog]] = asyncio.Queue(
            maxsize=200,
        )
        self.dialogs: list[BrowserDialogDescriptor] = []
        self.dialog_objects: dict[str, Dialog] = {}
        self.next_dialog_id = next_dialog_id
        self.page_open_queue: asyncio.Queue[Page] = asyncio.Queue(maxsize=100)
        self.page_close_queue: asyncio.Queue[Page] = asyncio.Queue(maxsize=200)
        self.known_page_ids: set[int] = set()
        self.console_queue: asyncio.Queue[BrowserConsoleMessage] = asyncio.Queue(maxsize=2000)
        self.console_messages: list[BrowserConsoleMessage] = []
        self.network_queue: asyncio.Queue[BrowserNetworkQueuedResponse] = asyncio.Queue(
            maxsize=2000,
        )
        self.network_requests: list[BrowserNetworkRequest] = []
        self.downloads_dir = downloads_dir
        self.download_queue: asyncio.Queue[PendingBrowserDownload] = asyncio.Queue(maxsize=200)
        self.download_tasks: dict[str, asyncio.Task[None]] = {}
        self.download_target_paths: set[str] = set()
        self.downloads: list[BrowserDownload] = []
        self.download_size_hints: list[tuple[str, int]] = []
        self.next_download_id = next_download_id
        self.console_last_call_index = console_last_call_index
        self.console_page_load_index = console_page_load_index
        self.network_last_call_index = network_last_call_index
        self.network_page_load_index = network_page_load_index
        self.last_touched_monotonic = time.monotonic()
        self.host_block_cache: set[str] = set()
        self.adblock_service = adblock_service
        self.context_closed: bool = False
        self.page_ref_states: dict[int, PageRefState] = {}
