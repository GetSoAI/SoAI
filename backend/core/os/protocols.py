"""SoAI - OS service protocols for API container wiring [backend/core/os/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from core.events.types_base import Event
from core.os.drivers_types import (
    DKMSStatusSnapshot,
    DriverStatusSnapshot,
    SecureBootStatus,
)
from core.os.enums import OSMode
from core.os.maintenance_types import (
    LogEntry,
    MaintenanceStatusSnapshot,
    SystemdServiceStatus,
    TimeSyncStatus,
)
from core.os.network_types import (
    NetworkConnection,
    NetworkConnectionConfig,
    NetworkConnectionProfile,
    NetworkDevice,
    NetworkStatusSnapshot,
)
from core.os.ssh_types import SshStatus
from core.os.status_types import OSStatusSnapshot
from core.os.storage_types import (
    BlockDevice,
    FstabEntry,
    FstabEntryConfig,
    Partition,
    StorageStatusSnapshot,
)
from core.os.types import OSCapabilities
from core.os.updates_types import (
    InstalledPackage,
    UpdateHistoryEntry,
    UpdatesCheckResult,
    UpdatesStatusSnapshot,
)
from core.os.users_types import SystemUserInfo, UserSyncStatusSnapshot

__all__ = (
    "OSDriversStatusServiceProtocol",
    "OSDriversTaskServiceProtocol",
    "OSMaintenanceLogsServiceProtocol",
    "OSMaintenancePowerServiceProtocol",
    "OSMaintenanceSshSafeDisableServiceProtocol",
    "OSMaintenanceSshServiceProtocol",
    "OSMaintenanceStatusServiceProtocol",
    "OSMaintenanceSystemdServiceProtocol",
    "OSMaintenanceTimeSyncServiceProtocol",
    "OSManagerProtocol",
    "OSNetworkSafeApplyServiceProtocol",
    "OSNetworkStatusServiceProtocol",
    "HostManagementServicesProtocol",
    "OSStorageMutationServiceProtocol",
    "OSStorageStatusServiceProtocol",
    "OSUpdatesStatusServiceProtocol",
    "OSUpdatesTaskServiceProtocol",
    "OSUserSyncServiceProtocol",
)


class OSManagerProtocol(Protocol):
    @property
    def enabled(self) -> bool: ...

    @property
    def mode(self) -> OSMode: ...

    async def get_capabilities(self) -> OSCapabilities: ...
    async def get_status(self, services: HostManagementServicesProtocol) -> OSStatusSnapshot: ...


class OSDriversStatusServiceProtocol(Protocol):
    async def get_driver_status(self) -> DriverStatusSnapshot: ...
    async def get_dkms_status(self) -> DKMSStatusSnapshot: ...
    async def get_secure_boot_status(self) -> SecureBootStatus: ...


class OSDriversTaskServiceProtocol(Protocol):
    async def handle_driver_install_command(self, command: Event) -> None: ...
    async def handle_driver_uninstall_command(self, command: Event) -> None: ...


class OSNetworkStatusServiceProtocol(Protocol):
    async def get_network_status(self) -> NetworkStatusSnapshot: ...
    async def list_connections(self) -> tuple[NetworkConnection, ...]: ...
    async def list_devices(self) -> tuple[NetworkDevice, ...]: ...
    async def get_connection(self, connection_id: str) -> NetworkConnection | None: ...
    async def get_connection_profile(
        self,
        connection_id: str,
    ) -> NetworkConnectionProfile | None: ...
    async def modify_connection(
        self,
        connection_id: str,
        config: NetworkConnectionConfig,
    ) -> NetworkConnection: ...
    async def delete_connection(self, connection_id: str) -> bool: ...


class OSNetworkSafeApplyServiceProtocol(Protocol):
    async def commit_safe_apply(self, task_id: str) -> bool: ...
    async def rollback_safe_apply(self, task_id: str) -> bool: ...


class OSStorageStatusServiceProtocol(Protocol):
    async def get_storage_status(self) -> StorageStatusSnapshot: ...
    async def list_block_devices(self) -> tuple[BlockDevice, ...]: ...
    async def get_block_device(self, device_path: str) -> BlockDevice | None: ...
    async def list_partitions(self, device_path: str) -> tuple[Partition, ...]: ...
    async def get_fstab_entries(self) -> tuple[FstabEntry, ...]: ...


class OSStorageMutationServiceProtocol(Protocol):
    async def handle_mutation_command(self, command: Event) -> None: ...
    async def ensure_partition_can_mount(self, partition_path: str) -> None: ...
    async def ensure_partition_can_unmount(self, partition_path: str) -> None: ...
    async def ensure_fstab_entry_can_add(self, entry: FstabEntryConfig) -> None: ...
    async def ensure_fstab_entry_can_remove(self, mount_point: str) -> None: ...


class OSUserSyncServiceProtocol(Protocol):
    enabled: bool

    async def get_sync_status(self) -> UserSyncStatusSnapshot: ...
    async def sync_user(self, webui_user_id: int) -> SystemUserInfo: ...
    async def lock_system_user(self, webui_user_id: int) -> bool: ...
    async def sync_ssh_keys(self, webui_user_id: int, public_keys: Sequence[str]) -> bool: ...
    async def get_system_user_mapping(self) -> dict[int, SystemUserInfo]: ...


class OSUpdatesStatusServiceProtocol(Protocol):
    async def get_updates_status(self) -> UpdatesStatusSnapshot: ...
    async def get_upgradable_packages_snapshot(self) -> UpdatesCheckResult | None: ...
    async def check_updates(self, *, force: bool) -> UpdatesCheckResult: ...
    async def list_installed_packages(
        self,
        *,
        package_filter: str | None,
    ) -> tuple[InstalledPackage, ...]: ...
    async def get_update_history(self, *, limit: int) -> tuple[UpdateHistoryEntry, ...]: ...
    async def is_reboot_required(self) -> bool: ...


class OSUpdatesTaskServiceProtocol(Protocol):
    async def handle_update_check_command(self, command: Event) -> None: ...
    async def handle_update_install_command(self, command: Event) -> None: ...


class OSMaintenanceStatusServiceProtocol(Protocol):
    async def get_maintenance_status(self) -> MaintenanceStatusSnapshot: ...


class OSMaintenanceSystemdServiceProtocol(Protocol):
    async def get_systemd_service_status(self, service_name: str) -> SystemdServiceStatus: ...
    async def control_systemd_service(
        self,
        service_name: str,
        action: str,
    ) -> SystemdServiceStatus: ...


class OSMaintenanceLogsServiceProtocol(Protocol):
    async def get_logs(
        self,
        *,
        unit: str | None,
        lines: int,
        since: str | None,
    ) -> tuple[LogEntry, ...]: ...


class OSMaintenanceTimeSyncServiceProtocol(Protocol):
    async def get_time_sync_status(self) -> TimeSyncStatus: ...


class OSMaintenancePowerServiceProtocol(Protocol):
    async def schedule_restart(self, *, delay_minutes: int, message: str | None) -> bool: ...
    async def schedule_shutdown(self, *, delay_minutes: int, message: str | None) -> bool: ...


class OSMaintenanceSshServiceProtocol(Protocol):
    async def get_ssh_status(self) -> SshStatus: ...
    async def enable_ssh(self) -> bool: ...


class OSMaintenanceSshSafeDisableServiceProtocol(Protocol):
    async def handle_ssh_safe_disable_command(self, command: Event) -> None: ...
    async def commit_ssh_disable(self, task_id: str) -> bool: ...
    async def rollback_ssh_disable(self, task_id: str) -> bool: ...


class HostManagementServicesProtocol(Protocol):
    @property
    def manager(self) -> OSManagerProtocol: ...
    @property
    def drivers_status(self) -> OSDriversStatusServiceProtocol: ...
    @property
    def drivers_tasks(self) -> OSDriversTaskServiceProtocol: ...
    @property
    def network_status(self) -> OSNetworkStatusServiceProtocol: ...
    @property
    def network_safe_apply(self) -> OSNetworkSafeApplyServiceProtocol: ...
    @property
    def storage_status(self) -> OSStorageStatusServiceProtocol: ...
    @property
    def storage_mutation(self) -> OSStorageMutationServiceProtocol: ...
    @property
    def users(self) -> OSUserSyncServiceProtocol: ...
    @property
    def updates_status(self) -> OSUpdatesStatusServiceProtocol: ...
    @property
    def updates_tasks(self) -> OSUpdatesTaskServiceProtocol: ...
    @property
    def maintenance_status(self) -> OSMaintenanceStatusServiceProtocol: ...
    @property
    def maintenance_systemd(self) -> OSMaintenanceSystemdServiceProtocol: ...
    @property
    def maintenance_logs(self) -> OSMaintenanceLogsServiceProtocol: ...
    @property
    def maintenance_time_sync(self) -> OSMaintenanceTimeSyncServiceProtocol: ...
    @property
    def maintenance_power(self) -> OSMaintenancePowerServiceProtocol: ...
    @property
    def ssh(self) -> OSMaintenanceSshServiceProtocol: ...
    @property
    def ssh_safe_disable(self) -> OSMaintenanceSshSafeDisableServiceProtocol: ...
