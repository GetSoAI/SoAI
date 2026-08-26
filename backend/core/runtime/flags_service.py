"""SoAI - Runtime flags service [backend/core/runtime/flags_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
from dataclasses import dataclass

from core.di.validation import require_dependencies

__all__ = (
    "RuntimeFlagsService",
    "RuntimeFlagsServiceDependencies",
)


@dataclass(frozen=True, slots=True)
class RuntimeFlagsServiceDependencies:
    initial_host_system_actions_disabled: bool = False
    initial_hardware_mutation_disabled: bool = False
    initial_offline_mode: bool = False
    initial_block_private_network_egress: bool = False
    dns_validation_timeout_sec: float = 3.0
    initial_host_management_available: bool = False

    def __post_init__(self) -> None:
        require_dependencies(
            owner="RuntimeFlagsServiceDependencies",
            dns_validation_timeout_sec=self.dns_validation_timeout_sec,
            initial_block_private_network_egress=self.initial_block_private_network_egress,
            initial_hardware_mutation_disabled=self.initial_hardware_mutation_disabled,
            initial_host_system_actions_disabled=self.initial_host_system_actions_disabled,
            initial_offline_mode=self.initial_offline_mode,
            initial_host_management_available=self.initial_host_management_available,
        )


class RuntimeFlagsService:
    __slots__ = (
        "_block_private_network_egress",
        "_dns_validation_timeout_sec",
        "_hardware_mutation_disabled",
        "_host_system_actions_disabled",
        "_lock",
        "_offline_mode",
        "_host_management_available",
    )

    def __init__(self, deps: RuntimeFlagsServiceDependencies) -> None:
        self._lock = threading.RLock()
        self._host_system_actions_disabled: bool = deps.initial_host_system_actions_disabled
        self._hardware_mutation_disabled: bool = deps.initial_hardware_mutation_disabled
        self._offline_mode: bool = deps.initial_offline_mode
        self._block_private_network_egress: bool = deps.initial_block_private_network_egress
        self._dns_validation_timeout_sec: float = max(0.1, deps.dns_validation_timeout_sec)
        self._host_management_available: bool = deps.initial_host_management_available

    @property
    def host_system_actions_disabled(self) -> bool:
        with self._lock:
            return self._host_system_actions_disabled

    @property
    def hardware_mutation_disabled(self) -> bool:
        with self._lock:
            return self._hardware_mutation_disabled

    @property
    def offline_mode(self) -> bool:
        with self._lock:
            return self._offline_mode

    @property
    def block_private_network_egress(self) -> bool:
        with self._lock:
            return self._block_private_network_egress

    @property
    def dns_validation_timeout_sec(self) -> float:
        with self._lock:
            return self._dns_validation_timeout_sec

    @property
    def host_management_available(self) -> bool:
        with self._lock:
            return self._host_management_available

    @property
    def host_management_enabled(self) -> bool:
        with self._lock:
            return self._host_management_available and not self._host_system_actions_disabled

    def update_runtime_policy(
        self,
        *,
        host_system_actions_disabled: bool,
        hardware_mutation_disabled: bool,
        offline_mode: bool,
        block_private_network_egress: bool,
        dns_validation_timeout_sec: float,
        host_management_available: bool,
    ) -> None:
        with self._lock:
            self._host_system_actions_disabled = host_system_actions_disabled
            self._hardware_mutation_disabled = hardware_mutation_disabled
            self._offline_mode = offline_mode
            self._block_private_network_egress = block_private_network_egress
            self._dns_validation_timeout_sec = max(0.1, dns_validation_timeout_sec)
            self._host_management_available = host_management_available
