"""SoAI - Preserved GPU alias profile history [backend/hardware/presets/slot_alias_history.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
import hashlib

from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable
from core.types.json import JSONDict
from core.types.json_value import require_json_dict

__all__ = ("preserve_alias_sources", "reassign_alias_history", "validate_alias_history")


def reassign_alias_history(payload: JSONDict, source_id: str, canonical: str) -> None:
    history = require_json_dict(payload.get("alias_history", {}), label="GPU alias history")
    if source_id == canonical or source_id not in history:
        return
    source = require_json_dict(history[source_id], label="GPU alias history records")
    destination = require_json_dict(history.get(canonical, {}), label="GPU alias history records")
    for revision, record in source.items():
        if revision in destination and destination[revision] != record:
            raise ValidationError("GPU alias history has conflicting preserved revisions.")
        destination[revision] = record
    history[canonical] = destination
    del history[source_id]
    payload["alias_history"] = history


def preserve_alias_sources(
    payload: JSONDict, canonical: str, sources: JSONDict, *, boot_conflict: bool
) -> None:
    history = require_json_dict(payload.get("alias_history", {}), label="GPU alias history")
    device_history = require_json_dict(history.get(canonical, {}), label="GPU alias history")
    revision = hashlib.sha256(serialize_json_compact_stable(sources).encode("utf-8")).hexdigest()
    record: JSONDict = {"sources": copy.deepcopy(sources), "boot_conflict": boot_conflict}
    if revision in device_history and device_history[revision] != record:
        raise ValidationError("GPU alias history conflicts with its preserved revision.")
    device_history[revision] = record
    history[canonical] = device_history
    payload["alias_history"] = history


def validate_alias_history(payload: JSONDict) -> None:
    history = require_json_dict(payload.get("alias_history", {}), label="GPU alias history")
    for canonical, device_history in history.items():
        if not canonical:
            raise ValidationError("GPU alias history requires a device identifier.")
        records = require_json_dict(device_history, label="GPU alias history records")
        for revision, record_value in records.items():
            record = require_json_dict(record_value, label="GPU alias history record")
            sources = require_json_dict(record.get("sources"), label="GPU alias history sources")
            if (
                set(record) != {"sources", "boot_conflict"}
                or not isinstance(record.get("boot_conflict"), bool)
                or not sources
                or revision
                != hashlib.sha256(
                    serialize_json_compact_stable(sources).encode("utf-8")
                ).hexdigest()
            ):
                raise ValidationError("GPU alias history has invalid preserved authority.")
            for device_id, entry in sources.items():
                if not device_id or not isinstance(entry, dict):
                    raise ValidationError("GPU alias history requires complete source entries.")
