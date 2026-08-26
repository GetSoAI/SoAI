"""SoAI - Routing configuration dataclasses and builder from raw JSON dicts [backend/core/orchestrator/routing_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from core.config.byte_sizes import MIB_BYTES
from core.errors.exceptions import ValidationError
from core.orchestrator.request_priority import validate_priority_aging_windows
from core.timing.constants import LONG_REQUEST_TIMEOUT_SEC
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict, JSONValue

__all__ = (
    "ConstituentModelConfig",
    "FailoverConfig",
    "RoutingConfig",
    "RoutingConfigHolder",
    "VirtualModelConfig",
    "build_effective_routing_config",
    "is_supported_virtual_model_strategy",
    "merge_routing_config",
    "merge_virtual_model_lists",
    "require_routing_config",
)

SUPPORTED_VIRTUAL_MODEL_STRATEGIES: frozenset[str] = frozenset({"load_balancing", "failover"})
_MIN_FREE_DISK_BYTES_FOR_ACCEPT_DEFAULT = 256 * MIB_BYTES


@dataclass(slots=True)
class ConstituentModelConfig:
    universal_id: str
    parameters: dict[str, JSONValue] = field(default_factory=dict[str, JSONValue])


@dataclass(slots=True)
class VirtualModelConfig:
    name: str
    strategy: str
    models: list[ConstituentModelConfig]
    created_at_ms: int = field(default_factory=epoch_ms)
    last_modified_at_ms: int = field(default_factory=epoch_ms)
    is_enabled: bool = True


@dataclass(slots=True)
class FailoverConfig:
    primary: str
    secondary: str


@dataclass(slots=True)
class RoutingConfig:
    max_concurrent_plugins: int = 2
    task_queue_max_size: int = 1000
    scheduler_safety_net_delay_sec: float = 0.5
    durable_queue_lease_ttl_sec: float = 30.0
    durable_queue_recovery_sweep_sec: float = 5.0
    durable_queue_hard_limit_tasks: int = 0
    min_free_disk_bytes_for_accept: int = _MIN_FREE_DISK_BYTES_FOR_ACCEPT_DEFAULT
    plugin_prefetch_window_default: int = 8
    standard_priority_aging_sec: float = 25.0
    flex_priority_aging_sec: float = 120.0
    cancel_on_client_disconnect: bool = False
    http_async_accept_default: bool = False
    acceptance_db_busy_timeout_sec: float = 30.0
    inference_task_retention_days: int = 180
    owner_running_limits_default: int = 4
    owner_running_limits_by_owner_type: dict[str, int] = field(default_factory=dict[str, int])
    deduplication_enabled: bool = True
    deduplication_keys: tuple[str, ...] = field(default_factory=tuple)
    prompt_queuing: bool = False
    queue_prompt_slot_limit: int = 4
    fair_task_rotation: bool = False
    virtual_models: list[VirtualModelConfig] = field(default_factory=list[VirtualModelConfig])
    failovers: list[FailoverConfig] = field(default_factory=list[FailoverConfig])
    health_checks: JSONDict = field(
        default_factory=lambda: {
            "INTERVAL_SEC": 20.0,
            "JITTER_FRACTION": 0.1,
            "STREAMING_IDLE_TIMEOUT_SEC": LONG_REQUEST_TIMEOUT_SEC,
            "NON_STREAMING_TIMEOUT_SEC": LONG_REQUEST_TIMEOUT_SEC,
            "STREAMING_PREFILL_MIN_TOKENS_PER_SEC": 50.0,
            "STREAMING_PREFILL_OVERHEAD_SEC": 60.0,
            "PING_TIMEOUT_SEC": 15.0,
            "STUCK_STATE_TIMEOUT_SEC": 900.0,
            "FLAPPING_WINDOW_SEC": 120.0,
            "FLAPPING_MIN_TRANSITIONS": 3,
            "PENDING_STARTUP_TASK_TIMEOUT_SEC": 0.0,
            "RECOVERY_TIMEOUT_SEC": 1440.0,
            "FAILURE_WINDOW_SEC": 1440.0,
            "MAX_RECOVERY_ATTEMPTS": 3,
            "NUM_PLANNER_WORKERS": 16,
            "FAIR_DISPATCH_ENABLED": True,
            "FAIR_DISPATCH_MAX_PER_PLUGIN": 32,
            "VIRTUAL_MODEL_FAILOVER_COOLDOWN_SEC": 15.0,
            "MAX_CONCURRENT_TASKS_PER_PLUGIN": {"DEFAULT": 4, "PER_PLUGIN": {}},
            "COMMAND_TIMEOUTS_SEC": {
                "PLUGIN_STOP": 300.0,
                "PLUGIN_LOAD_MODEL": 7200.0,
            },
        },
    )

    def __post_init__(self) -> None:
        validate_priority_aging_windows(
            self.standard_priority_aging_sec,
            self.flex_priority_aging_sec,
        )


class RoutingConfigHolder:
    def __init__(self, routing_config: RoutingConfig) -> None:
        self._base_routing_config = copy.deepcopy(routing_config)
        self._database_virtual_models: list[VirtualModelConfig] = []

    @property
    def base_routing_config(self) -> RoutingConfig:
        return copy.deepcopy(self._base_routing_config)

    @property
    def routing_config(self) -> RoutingConfig:
        return build_effective_routing_config(
            base=self._base_routing_config,
            database_virtual_models=self._database_virtual_models,
        )

    @routing_config.setter
    def routing_config(self, value: RoutingConfig) -> None:
        self._base_routing_config = copy.deepcopy(value)

    def replace_effective_sources(
        self,
        *,
        routing_config: RoutingConfig,
        database_virtual_models: list[VirtualModelConfig],
    ) -> RoutingConfig:
        self._base_routing_config = copy.deepcopy(routing_config)
        self._database_virtual_models = copy.deepcopy(database_virtual_models)
        return self.routing_config

    def replace_database_virtual_models(
        self,
        database_virtual_models: list[VirtualModelConfig],
    ) -> RoutingConfig:
        self._database_virtual_models = copy.deepcopy(database_virtual_models)
        return self.routing_config

    def list_virtual_models(self) -> list[VirtualModelConfig]:
        return list(self.routing_config.virtual_models)

    def get_virtual_model(self, name: str) -> VirtualModelConfig | None:
        normalized_name = name.strip()
        if not normalized_name:
            return None
        for virtual_model in self.routing_config.virtual_models:
            if virtual_model.name == normalized_name:
                return virtual_model
        return None

    def has_base_virtual_model(self, name: str) -> bool:
        normalized_name = name.strip()
        if not normalized_name:
            return False
        for virtual_model in self._base_routing_config.virtual_models:
            if virtual_model.name == normalized_name:
                return True
        return False


def is_supported_virtual_model_strategy(strategy: str) -> bool:
    normalized_strategy = strategy.strip()
    return normalized_strategy in SUPPORTED_VIRTUAL_MODEL_STRATEGIES


def merge_virtual_model_lists(
    *,
    primary: list[VirtualModelConfig],
    secondary: list[VirtualModelConfig],
) -> list[VirtualModelConfig]:
    merged: list[VirtualModelConfig] = []
    seen_names: set[str] = set()
    for source in (primary, secondary):
        for virtual_model in source:
            if not isinstance(virtual_model, VirtualModelConfig):
                continue
            name = virtual_model.name.strip()
            if not name or name in seen_names:
                continue
            merged.append(copy.deepcopy(virtual_model))
            seen_names.add(name)
    return merged


def merge_routing_config(
    *,
    base: RoutingConfig | None,
    incoming: RoutingConfig | None,
    virtual_models: list[VirtualModelConfig] | None,
    failovers: list[FailoverConfig] | None,
) -> RoutingConfig:
    source = incoming if incoming is not None else base if base is not None else RoutingConfig()
    merged: RoutingConfig = copy.deepcopy(source)
    if virtual_models is not None:
        merged.virtual_models = list(virtual_models)
    if failovers is not None:
        merged.failovers = list(failovers)
    return merged


def build_effective_routing_config(
    *,
    base: RoutingConfig,
    database_virtual_models: list[VirtualModelConfig],
) -> RoutingConfig:
    effective_virtual_models = merge_virtual_model_lists(
        primary=list(base.virtual_models),
        secondary=database_virtual_models,
    )
    return merge_routing_config(
        base=base,
        incoming=None,
        virtual_models=effective_virtual_models,
        failovers=list(base.failovers),
    )


def require_routing_config(
    routing_config: RoutingConfig | None,
    *,
    missing_message: str = "Routing config has not been initialized.",
    error_type: type[Exception] = ValidationError,
) -> RoutingConfig:
    if routing_config is None:
        raise error_type(missing_message)
    return routing_config
