"""SoAI - Model record fingerprinting and upsert preparation [backend/models/discovery/record_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import TYPE_CHECKING, TypedDict

from core.errors.exceptions import ValidationError
from core.models.context_window import extract_context_window_tokens_from_metadata
from core.models.universal_id import generate_universal_id
from core.serialization.json import serialize_json_compact_stable_strict
from core.timing.epoch import epoch_ms
from models.discovery.provider_bounded_execution import PluginCheckUnchanged

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "IndexedModelCandidates",
    "PreparedModelUpserts",
    "index_model_candidates",
    "model_fingerprint_records",
    "prepare_model_upserts",
)


def _require_discovered_source_model_id(data: JSONDict) -> str | None:
    source_model_id_value = data.get("source_model_id")
    if not isinstance(source_model_id_value, str):
        return None
    source_model_id = source_model_id_value.strip()
    return source_model_id or None


def model_fingerprint_records(records: list[JSONDict]) -> str | None:
    if not records:
        return None
    volatile_keys = {
        "last_discovered_at_ms",
        "last_used_at_ms",
        "request_count",
    }
    fingerprints: list[str] = []
    for record in records:
        filtered: JSONDict = {
            key: value for key, value in record.items() if key not in volatile_keys
        }
        universal_id = record.get("universal_id")
        if not isinstance(universal_id, str) or not universal_id:
            raise ValidationError("Model record is missing universal_id.")
        payload = serialize_json_compact_stable_strict(filtered)
        fingerprints.append(f"{universal_id}:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}")
    return "|".join(sorted(fingerprints))


class PreparedModelUpserts(TypedDict):
    models_to_upsert: list[JSONDict]
    added_universal_ids: list[str]
    all_discovered_universal_ids_by_plugin: dict[str, set[str]]


class IndexedModelCandidates(TypedDict):
    candidate_records_by_universal_id: dict[str, JSONDict]
    all_discovered_universal_ids_by_plugin: dict[str, set[str]]


def index_model_candidates(
    discovered_data: dict[
        str,
        dict[str, JSONDict] | Exception | PluginCheckUnchanged | None,
    ],
) -> IndexedModelCandidates:
    candidate_records_by_universal_id: dict[str, JSONDict] = {}
    all_discovered_universal_ids_by_plugin: dict[str, set[str]] = defaultdict(set)
    discovery_timestamp_ms = int(epoch_ms())
    for plugin_name, models in discovered_data.items():
        if not isinstance(models, dict):
            continue
        for model_id, data in models.items():
            source_model_id = _require_discovered_source_model_id(data)
            if not source_model_id:
                raise ValidationError(
                    "Discovered model is missing required field 'source_model_id'.",
                    details={"plugin_name": plugin_name, "model_id": model_id},
                )
            universal_id = generate_universal_id(plugin_name, source_model_id)
            if not universal_id:
                raise ValidationError(
                    "Failed to generate universal_id for discovered model.",
                    details={
                        "plugin_name": plugin_name,
                        "model_id": model_id,
                        "source_model_id": source_model_id,
                    },
                )
            if universal_id in candidate_records_by_universal_id:
                raise ValidationError(
                    "Discovery returned duplicate model source identities.",
                    details={
                        "plugin_name": plugin_name,
                        "model_id": model_id,
                        "source_model_id": source_model_id,
                        "universal_id": universal_id,
                    },
                )
            all_discovered_universal_ids_by_plugin[plugin_name].add(universal_id)
            filtered_data = {
                key: value for key, value in data.items() if key not in {"source_model_id"}
            }
            new_record = {
                **filtered_data,
                "plugin_name": plugin_name,
                "model_id": model_id,
                "source_model_id": source_model_id,
                "universal_id": universal_id,
                "last_discovered_at_ms": discovery_timestamp_ms,
            }
            if "context_window_tokens" not in new_record:
                context_window_tokens = extract_context_window_tokens_from_metadata(data)
                if context_window_tokens is not None:
                    new_record["context_window_tokens"] = context_window_tokens
            candidate_records_by_universal_id[universal_id] = new_record
    return {
        "candidate_records_by_universal_id": candidate_records_by_universal_id,
        "all_discovered_universal_ids_by_plugin": all_discovered_universal_ids_by_plugin,
    }


def prepare_model_upserts(
    indexed_candidates: IndexedModelCandidates,
    existing_models_by_plugin: dict[str, dict[str, JSONDict]],
) -> PreparedModelUpserts:
    existing_by_universal_id: dict[str, JSONDict] = {}
    for models in existing_models_by_plugin.values():
        for stored_record in models.values():
            universal_id = stored_record.get("universal_id")
            if isinstance(universal_id, str) and universal_id:
                existing_by_universal_id[universal_id] = stored_record
    models_to_upsert: list[JSONDict] = []
    added_universal_ids: list[str] = []
    preserved_fields = (
        "created_at_ms",
        "description",
        "display_name",
        "is_enabled",
        "last_used_at_ms",
        "openai_capabilities_overrides",
        "parameter_version",
        "request_count",
    )
    for candidate_record in indexed_candidates["candidate_records_by_universal_id"].values():
        universal_id_value = candidate_record.get("universal_id")
        if not isinstance(universal_id_value, str) or not universal_id_value:
            raise ValidationError("Indexed model candidate is missing universal_id.")
        authoritative_record = existing_by_universal_id.get(universal_id_value)
        if authoritative_record is None:
            added_universal_ids.append(universal_id_value)
            models_to_upsert.append(candidate_record)
            continue
        merged_record = {**authoritative_record, **candidate_record}
        for field_name in preserved_fields:
            if field_name in authoritative_record:
                merged_record[field_name] = authoritative_record[field_name]
        models_to_upsert.append(merged_record)
    return {
        "models_to_upsert": models_to_upsert,
        "added_universal_ids": added_universal_ids,
        "all_discovered_universal_ids_by_plugin": indexed_candidates[
            "all_discovered_universal_ids_by_plugin"
        ],
    }
