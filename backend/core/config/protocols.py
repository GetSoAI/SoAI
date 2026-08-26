"""SoAI - Core config protocols [backend/core/config/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol, overload, runtime_checkable

from core.config.value_types import ConfigValue

if TYPE_CHECKING:
    from collections.abc import Callable

    from ruamel.yaml.comments import CommentedMap

    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ConfigIOProtocol",
    "ConfigManagerProtocol",
    "ConfigProtocol",
    "ConfigValue",
    "CoreConfigReloadClassification",
    "CoreConfigReloadCoordinatorProtocol",
    "CoreConfigReloadEventProtocol",
    "CoreConfigReloadResult",
    "ReloadRejectionReason",
)


@runtime_checkable
class ConfigProtocol(Protocol):
    @overload
    def get(self, key: str, default: ConfigValue) -> ConfigValue: ...

    @overload
    def get(self, key: str, default: ConfigValue | None = None) -> ConfigValue | None: ...

    def get(self, key: str, default: ConfigValue | None = None) -> ConfigValue | None: ...

    def get_int(self, key: str, default: int = 0) -> int: ...

    def get_float(self, key: str, default: float = 0.0) -> float: ...

    def get_bool(self, key: str, default: bool = False) -> bool: ...

    @overload
    def get_str(self, key: str, default: str) -> str: ...

    @overload
    def get_str(self, key: str, default: str | None = None) -> str | None: ...

    def get_str(self, key: str, default: str | None = None) -> str | None: ...

    def require_str(self, key: str) -> str: ...

    def require_str_value(self, key: str) -> str: ...


class ConfigIOProtocol(Protocol):
    lock_directory: str | None

    def get_config_path_sync(self, config_name: str) -> str: ...

    def path_to_config_name(self, path: str) -> str | None: ...

    def parse_config_contents(
        self,
        raw_contents: str,
        *,
        config_name: str,
        config_path: str,
    ) -> ConfigValue: ...

    async def read_config_snapshot(
        self,
        *,
        config_path: str,
        config_name: str,
    ) -> tuple[str, str | None]: ...

    async def read_config_from_disk(self, *, config_name: str) -> ConfigValue: ...

    async def calculate_file_hash(self, path: str) -> str | None: ...


class ConfigManagerProtocol(Protocol):
    def get_lock_path(self, path: str) -> str: ...

    def get_config_path_sync(self, config_name: str) -> str: ...

    def creation_lock_for(self, key: str) -> AbstractAsyncContextManager[None]: ...

    def plugin_config_mutation_scope(
        self,
        config_name: str,
    ) -> AbstractAsyncContextManager[None]: ...

    async def establish_baseline(self) -> None: ...

    def start(self) -> None: ...

    async def load_config(self, config_name: str, force_reload: bool = False) -> ConfigValue: ...

    async def delete_from_cache(self, config_name: str) -> None: ...

    async def save_config(
        self,
        config_name: str,
        data: ConfigValue | None = None,
        *,
        source: str,
        changed_keys: frozenset[str] | None = None,
    ) -> bool: ...

    async def update_config_transactionally(
        self,
        config_name: str,
        *,
        source: str,
        updater: Callable[[CommentedMap], CommentedMap | dict[str, JSONValue]],
        changed_keys: frozenset[str] | None = None,
    ) -> bool: ...

    async def build_clone_configuration_snapshot(
        self,
        source_name: str,
        field_overrides: Mapping[str, JSONValue] | None = None,
    ) -> tuple[JSONDict, JSONDict] | None: ...

    async def stage_config(
        self,
        config_path: str,
        data: JSONDict,
        reservation: DiskSpaceReservationLeaseProtocol,
        maximum_bytes: int,
    ) -> None: ...

    async def rescan_and_update_baseline_for_config(self, config_name: str) -> None: ...

    async def list_manageable_configs(self) -> list[str]: ...

    async def shutdown(self) -> None: ...


class ReloadRejectionReason(Enum):
    NOT_CORE_CONFIG = "not_core_config"
    STALE_REVISION = "stale_revision"
    INVALID_PAYLOAD = "invalid_payload"


@dataclass(frozen=True, slots=True)
class CoreConfigReloadClassification:
    revision: int
    changed_keys: frozenset[str]
    has_routing_changes: bool
    has_rate_limiting_changes: bool
    requires_restart: bool
    config_dict: JSONDict


@dataclass(frozen=True, slots=True)
class CoreConfigReloadResult:
    classification: CoreConfigReloadClassification | None
    rejection_reason: ReloadRejectionReason | None


@runtime_checkable
class CoreConfigReloadEventProtocol(Protocol):
    config_name: str
    revision: int
    changed_keys: frozenset[str]
    config_dict: JSONDict


@runtime_checkable
class CoreConfigReloadCoordinatorProtocol(Protocol):
    def try_accept_reload(
        self,
        event: CoreConfigReloadEventProtocol,
    ) -> CoreConfigReloadResult: ...
