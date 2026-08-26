"""SoAI - Core OS aggregated status types [backend/core/os/status_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field

from core.os.drivers_types import DriverStatusSnapshot
from core.os.enums import OSMode
from core.os.maintenance_types import MaintenanceStatusSnapshot, TimeSyncStatus
from core.os.network_types import NetworkStatusSnapshot
from core.os.ssh_types import SshStatus
from core.os.storage_types import StorageStatusSnapshot
from core.os.types import OSCapabilities
from core.os.updates_types import UpdatesStatusSnapshot
from core.os.users_types import UserSyncStatusSnapshot
from core.timing.epoch import epoch_ms

__all__ = ("OSStatusSnapshot",)


@dataclass(frozen=True, slots=True)
class OSStatusSnapshot:
    enabled: bool
    mode: OSMode
    capabilities: OSCapabilities
    drivers: DriverStatusSnapshot
    network: NetworkStatusSnapshot
    storage: StorageStatusSnapshot
    updates: UpdatesStatusSnapshot
    users: UserSyncStatusSnapshot
    ssh: SshStatus
    maintenance: MaintenanceStatusSnapshot
    time_sync: TimeSyncStatus
    timestamp_ms: int = field(default_factory=epoch_ms)
