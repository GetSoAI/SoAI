"""SoAI - Absolute-path preview resolution state [backend/features/api/routes/webui/absolute_paths_resolution_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.files.protocols import FileExplorerCoreProtocol
    from core.files.protocols_explorer import FileSystemRootScopeProtocol
    from core.logging.protocols import LoggerProtocol

__all__ = ("AbsolutePathsResolutionState",)


@dataclass(frozen=True, slots=True)
class AbsolutePathsResolutionState:
    file_explorer_core: FileExplorerCoreProtocol
    user_root_scope: FileSystemRootScopeProtocol
    effective_root_real: str
    override_workspace_path: str | None
    override_is_valid: bool
    override_validation_message: str | None
    logger: LoggerProtocol
