"""SoAI - Durable inference acceptance policy resolution [backend/database/repositories/tasks/durable_acceptance_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.default_schema.routing import build_routing_defaults
from core.config.factory import build_config
from core.config.protocols import ConfigProtocol
from core.config.schema_reconciliation import reconcile_config_schema
from core.config.value_validation import is_config_dict
from core.errors.exceptions import StateError, ValidationError

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict
    from core.types.json import JSONDict

__all__ = (
    "DurableAcceptancePolicy",
    "build_durable_acceptance_policy",
    "rebuild_durable_acceptance_policy",
)

_POLICY_ROUTING_FIELDS: tuple[str, ...] = (
    "DURABLE_QUEUE_HARD_LIMIT_TASKS",
    "MIN_FREE_DISK_BYTES_FOR_ACCEPT",
    "ACCEPTANCE_DB_BUSY_TIMEOUT_SEC",
)


@dataclass(frozen=True, slots=True)
class DurableAcceptancePolicy:
    durable_queue_hard_limit_tasks: int
    min_free_disk_bytes_for_accept: int
    acceptance_db_busy_timeout_sec: float
    filesystem_path: str


def build_durable_acceptance_policy(
    config: ConfigProtocol,
    *,
    database_path: str,
) -> DurableAcceptancePolicy:
    return _build_policy(
        config,
        filesystem_path=_resolve_durable_acceptance_filesystem_path(
            config=config,
            database_path=database_path,
        ),
    )


def rebuild_durable_acceptance_policy(
    config_dict: JSONDict,
    *,
    application_base_path: str,
    filesystem_path: str,
) -> DurableAcceptancePolicy:
    if not is_config_dict(config_dict):
        raise ValidationError("Core configuration snapshot contains unsupported values.")
    reconciled = reconcile_config_schema(schema=_policy_schema(), user=config_dict)
    return _build_policy(
        build_config({**config_dict, **reconciled.merged}, main_app_base_dir=application_base_path),
        filesystem_path=filesystem_path,
    )


def _policy_schema() -> ConfigDict:
    routing_defaults = build_routing_defaults().get("ROUTING")
    if not isinstance(routing_defaults, Mapping):
        raise StateError("Routing configuration defaults are unavailable.")
    return {
        "MODELS": {
            "ROUTING": {name: routing_defaults[name] for name in _POLICY_ROUTING_FIELDS},
        },
    }


def _build_policy(config: ConfigProtocol, *, filesystem_path: str) -> DurableAcceptancePolicy:
    return DurableAcceptancePolicy(
        durable_queue_hard_limit_tasks=max(
            0,
            int(config.get_int("MODELS.ROUTING.DURABLE_QUEUE_HARD_LIMIT_TASKS")),
        ),
        min_free_disk_bytes_for_accept=max(
            0,
            int(config.get_int("MODELS.ROUTING.MIN_FREE_DISK_BYTES_FOR_ACCEPT")),
        ),
        acceptance_db_busy_timeout_sec=max(
            0.0,
            float(config.get_float("MODELS.ROUTING.ACCEPTANCE_DB_BUSY_TIMEOUT_SEC")),
        ),
        filesystem_path=filesystem_path,
    )


def _resolve_durable_acceptance_filesystem_path(
    *,
    config: ConfigProtocol,
    database_path: str,
) -> str:
    for candidate in (
        database_path,
        config.get_str("DATA.DATABASE.PATHS.SYSTEM_DB"),
        config.get_str("SYSTEM.PATHS.SYSTEM_DATA"),
    ):
        normalized = _normalize_path_candidate(candidate)
        if normalized is None:
            continue
        return os.path.abspath(_resolve_existing_filesystem_root(normalized))
    return os.path.abspath(".")


def _normalize_path_candidate(candidate: str | None) -> str | None:
    if not isinstance(candidate, str):
        return None
    normalized = candidate.strip()
    if not normalized or normalized == ":memory:" or normalized.startswith("file:"):
        return None
    return normalized


def _resolve_existing_filesystem_root(candidate: str) -> str:
    if os.path.isdir(candidate):
        return candidate
    directory = os.path.dirname(candidate)
    if directory:
        return directory
    return "."
