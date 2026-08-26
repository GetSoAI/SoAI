"""SoAI - API runtime container protocols [backend/features/api/runtime/container/protocol_groups/container_protocols/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import Protocol, override

from core.runtime.protocols import RuntimeHealthViewProtocol
from core.state.protocols import RestartStateManagerProtocol
from features.api.runtime.container.auth_config import AuthConfig

__all__ = (
    "MetadataProtocol",
    "PathsContainerProtocol",
    "RuntimeContainerProtocol",
    "SecurityContainerProtocol",
)


class RuntimeContainerProtocol(RuntimeHealthViewProtocol, Protocol):
    @property
    def shutdown_event(self) -> asyncio.Event: ...

    @property
    @override
    def restart_pending(self) -> asyncio.Event: ...

    @property
    def startup_ready_event(self) -> asyncio.Event: ...

    @property
    def restart_state_manager(self) -> RestartStateManagerProtocol | None: ...


class PathsContainerProtocol(Protocol):
    @property
    def base_dir(self) -> str: ...

    @property
    def main_venv_dir(self) -> str: ...


class SecurityContainerProtocol(Protocol):
    @property
    def primary_signing_secret(self) -> str: ...

    @property
    def verification_secrets(self) -> tuple[str, ...]: ...

    @property
    def auth_config(self) -> AuthConfig: ...


class MetadataProtocol(Protocol):
    @property
    def version(self) -> str: ...
