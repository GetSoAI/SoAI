"""SoAI - Virtual model and failover config builders [backend/core/orchestrator/virtual_model_config_builders.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.protocols import LoggerProtocol
from core.orchestrator.routing_config import (
    ConstituentModelConfig,
    FailoverConfig,
    VirtualModelConfig,
    is_supported_virtual_model_strategy,
)
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "build_failover_configs",
    "build_virtual_model_configs",
)


def build_virtual_model_configs(
    entries: JSONValue,
    logger: LoggerProtocol,
) -> list[VirtualModelConfig]:
    configs: list[VirtualModelConfig] = []
    if not isinstance(entries, list):
        if entries:
            logger.warning("Ignoring invalid virtual model list in routing configuration.")
        return configs
    for entry in entries:
        virtual_model = coerce_virtual_model(entry, logger)
        if virtual_model:
            configs.append(virtual_model)
    return configs


def coerce_virtual_model(entry: JSONValue, logger: LoggerProtocol) -> VirtualModelConfig | None:
    if not isinstance(entry, dict):
        logger.warning("Virtual model definition must be a mapping. Skipping invalid entry.")
        return None
    name_raw = entry.get("name")
    strategy_raw = entry.get("strategy")
    models_data = entry.get("models")
    name = name_raw.strip() if isinstance(name_raw, str) else ""
    strategy = strategy_raw.strip() if isinstance(strategy_raw, str) else ""
    if not name or not strategy or (not isinstance(models_data, list)):
        logger.warning("Virtual model definition missing required fields. Entry: %s", entry)
        return None
    if not is_supported_virtual_model_strategy(strategy):
        logger.warning(
            "Virtual model definition has unsupported strategy '%s'. Entry: %s",
            strategy,
            entry,
        )
        return None
    constituents: list[ConstituentModelConfig] = []
    seen_universal_ids: set[str] = set()
    for model_entry in models_data:
        if not isinstance(model_entry, dict):
            logger.warning("Constituent definition must be a mapping in virtual model '%s'.", name)
            return None
        universal_id_raw = model_entry.get("universal_id")
        universal_id = universal_id_raw.strip() if isinstance(universal_id_raw, str) else ""
        if not universal_id:
            logger.warning(
                "Constituent model missing universal_id in virtual model '%s'.",
                name,
            )
            return None
        if universal_id in seen_universal_ids:
            logger.warning(
                "Virtual model '%s' contains duplicate constituent model '%s'.",
                name,
                universal_id,
            )
            return None
        parameters_raw = model_entry.get("parameters", {})
        parameters: dict[str, JSONValue] = {}
        if isinstance(parameters_raw, dict):
            for key, value in parameters_raw.items():
                if not isinstance(key, str):
                    logger.warning(
                        "Constituent parameters must have string keys in virtual model '%s'.",
                        name,
                    )
                    return None
                parameters[key] = value
        constituents.append(
            ConstituentModelConfig(universal_id=universal_id, parameters=parameters),
        )
        seen_universal_ids.add(universal_id)
    if len(constituents) < 2:
        logger.warning("Virtual model '%s' must define at least two constituent models.", name)
        return None
    created_at_raw = entry.get("created_at_ms")
    last_modified_at_raw = entry.get("last_modified_at_ms")
    now_ts = epoch_ms()
    created_value = (
        int(created_at_raw)
        if isinstance(created_at_raw, int | float) and not isinstance(created_at_raw, bool)
        else now_ts
    )
    last_modified_at_value = (
        int(last_modified_at_raw)
        if isinstance(last_modified_at_raw, int | float)
        and not isinstance(last_modified_at_raw, bool)
        else created_value
    )
    return VirtualModelConfig(
        name=name,
        strategy=strategy,
        models=constituents,
        created_at_ms=created_value,
        last_modified_at_ms=last_modified_at_value,
    )


def build_failover_configs(entries: JSONValue, logger: LoggerProtocol) -> list[FailoverConfig]:
    configs: list[FailoverConfig] = []
    raw_entries = entries or []
    if not isinstance(raw_entries, list):
        logger.warning("Ignoring invalid failover list in routing configuration.")
        return configs
    for entry in raw_entries:
        if not isinstance(entry, dict):
            logger.warning("Failover definition must be a mapping. Skipping invalid entry.")
            continue
        primary_raw = entry.get("primary")
        secondary_raw = entry.get("secondary")
        primary = primary_raw.strip() if isinstance(primary_raw, str) else ""
        secondary = secondary_raw.strip() if isinstance(secondary_raw, str) else ""
        if not primary or not secondary:
            logger.warning("Failover definition missing required endpoints. Entry: %s", entry)
            continue
        configs.append(FailoverConfig(primary=primary, secondary=secondary))
    return configs
