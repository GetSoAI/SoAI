"""SoAI - Tolerant stored chat preset V1 projection [backend/core/chat_presets/stored_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.chat_presets.canonicalization import canonicalize_chat_preset_field
from core.chat_presets.constants import (
    CHAT_PRESET_MAX_SECTIONS_JSON_BYTES,
    CHAT_PRESET_SECTION_IDS,
    CHAT_PRESET_TOOL_MODES,
    chat_preset_section_fields,
)
from core.chat_presets.contracts import ChatPresetProjectedRecord
from core.chat_presets.identity import (
    canonicalize_chat_preset_name,
    chat_preset_name_key,
    require_chat_preset_id,
)
from core.errors.exceptions import StateError, ValidationError
from core.rag.parameter_validation import validate_chunking_window
from core.serialization.json_parsing import MAX_JSON_NESTING_DEPTH, parse_json_value
from core.types.json import JSONDict, JSONValue
from core.validation.epoch import is_unix_epoch_ms
from core.validation.integers import is_positive_strict_int, is_strict_int
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX

__all__ = (
    "ChatPresetStoredIntegrityError",
    "project_stored_chat_preset",
)


class ChatPresetStoredIntegrityError(StateError):
    __slots__ = ()


def _integrity_failure() -> ChatPresetStoredIntegrityError:
    return ChatPresetStoredIntegrityError("Stored chat preset record is structurally invalid.")


def _required_row_value(row: Mapping[str, JSONValue], key: str) -> JSONValue:
    if key not in row:
        raise _integrity_failure()
    return row[key]


def _project_metadata(row: Mapping[str, JSONValue]) -> tuple[str, str, int, int, int]:
    preset_id = _required_row_value(row, "id")
    user_id = _required_row_value(row, "user_id")
    name = _required_row_value(row, "name")
    name_key = _required_row_value(row, "name_key")
    revision = _required_row_value(row, "revision")
    created_at_ms = _required_row_value(row, "created_at_ms")
    modified_at_ms = _required_row_value(row, "modified_at_ms")
    try:
        preset_id = require_chat_preset_id(preset_id)
    except ValidationError as exception:
        raise _integrity_failure() from exception
    if not is_positive_strict_int(user_id) or user_id > JAVASCRIPT_SAFE_INTEGER_MAX:
        raise _integrity_failure()
    try:
        canonical_name = canonicalize_chat_preset_name(name)
    except ValidationError as exception:
        raise _integrity_failure() from exception
    if name != canonical_name or not isinstance(name_key, str):
        raise _integrity_failure()
    try:
        if chat_preset_name_key(canonical_name) != name_key:
            raise _integrity_failure()
    except (UnicodeError, ValidationError) as exception:
        raise _integrity_failure() from exception
    if (
        not is_positive_strict_int(revision)
        or revision > JAVASCRIPT_SAFE_INTEGER_MAX
        or not is_unix_epoch_ms(created_at_ms)
        or not is_unix_epoch_ms(modified_at_ms)
        or modified_at_ms < created_at_ms
    ):
        raise _integrity_failure()
    return preset_id, canonical_name, revision, created_at_ms, modified_at_ms


def _decode_sections(row: Mapping[str, JSONValue]) -> JSONDict:
    raw_sections = _required_row_value(row, "sections_json")
    if not isinstance(raw_sections, str):
        raise _integrity_failure()
    try:
        if len(raw_sections.encode("utf-8")) > CHAT_PRESET_MAX_SECTIONS_JSON_BYTES:
            raise _integrity_failure()
        decoded = parse_json_value(
            raw_sections,
            field="stored chat preset sections",
            max_depth=MAX_JSON_NESTING_DEPTH,
            reject_duplicate_keys=True,
        )
    except (UnicodeError, ValidationError) as exception:
        raise _integrity_failure() from exception
    if not isinstance(decoded, dict):
        raise _integrity_failure()
    return decoded


def _canonical_dynamic_key(raw_key: str) -> str | None:
    try:
        canonical = canonicalize_chat_preset_field(
            "tools",
            "servers",
            {raw_key: True},
        )
    except ValidationError:
        return None
    if not isinstance(canonical, dict) or len(canonical) != 1:
        return None
    for canonical_key in canonical:
        if isinstance(canonical_key, str):
            return canonical_key
    return None


def _project_boolean_map(value: JSONValue) -> tuple[dict[str, bool] | None, int]:
    if not isinstance(value, Mapping) or not value:
        return None, 1
    canonical_keys: dict[str, list[str]] = {}
    for raw_key in value:
        canonical_key = _canonical_dynamic_key(raw_key)
        if canonical_key is not None:
            if canonical_key not in canonical_keys:
                canonical_keys[canonical_key] = []
            canonical_keys[canonical_key].append(raw_key)
    collisions = {
        raw_key for raw_keys in canonical_keys.values() if len(raw_keys) > 1 for raw_key in raw_keys
    }
    projected: dict[str, bool] = {}
    omitted = 0
    for raw_key, raw_value in value.items():
        canonical_key = _canonical_dynamic_key(raw_key)
        if canonical_key is None or raw_key in collisions or not isinstance(raw_value, bool):
            omitted += 1
            continue
        projected[canonical_key] = raw_value
    return (projected or None), omitted


def _project_modes(value: JSONValue) -> tuple[dict[str, dict[str, bool]] | None, int]:
    if not isinstance(value, Mapping) or not value:
        return None, 1
    projected: dict[str, dict[str, bool]] = {}
    omitted = 0
    for mode, tool_map in value.items():
        if mode not in CHAT_PRESET_TOOL_MODES:
            omitted += 1
            continue
        projected_map, map_omitted = _project_boolean_map(tool_map)
        omitted += map_omitted
        if projected_map is not None:
            projected[mode] = projected_map
    return (projected or None), omitted


def _project_field(section: str, field: str, value: JSONValue) -> tuple[JSONValue, int]:
    if section == "tools" and field == "servers":
        projected_servers, servers_omitted = _project_boolean_map(value)
        return projected_servers, servers_omitted
    if section == "tools" and field == "modes":
        projected_modes, modes_omitted = _project_modes(value)
        return projected_modes, modes_omitted
    try:
        return canonicalize_chat_preset_field(section, field, value), 0
    except (UnicodeError, ValidationError):
        return None, 1


def _remove_invalid_chunk_window(section: JSONDict) -> int:
    required = {"chunking_strategy", "chunk_size", "chunk_overlap"}
    if not required.issubset(section):
        return 0
    strategy = section["chunking_strategy"]
    chunk_size = section["chunk_size"]
    chunk_overlap = section["chunk_overlap"]
    if (
        not isinstance(strategy, str)
        or not is_strict_int(chunk_size)
        or not is_strict_int(chunk_overlap)
    ):
        return 0
    try:
        validate_chunking_window(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            chunking_strategy=strategy,
        )
    except ValidationError:
        del section["chunk_overlap"]
        return 1
    return 0


def _project_section(section: str, value: JSONValue) -> tuple[JSONDict | None, int]:
    if not isinstance(value, Mapping) or not value:
        return None, 1
    projected: JSONDict = {}
    omitted = 0
    fields = chat_preset_section_fields(section)
    if fields is None:
        return None, 1
    for field, field_value in value.items():
        if field not in fields:
            omitted += 1
            continue
        projected_value, field_omitted = _project_field(section, field, field_value)
        omitted += field_omitted
        if field_omitted == 0 or projected_value is not None:
            projected[field] = projected_value
    if section == "knowledge":
        omitted += _remove_invalid_chunk_window(projected)
    return (projected or None), omitted


def _project_sections(stored: JSONDict) -> tuple[JSONDict, int]:
    projected: JSONDict = {}
    omitted = 0
    for section, section_value in stored.items():
        if section not in CHAT_PRESET_SECTION_IDS:
            omitted += 1
            continue
        projected_section, section_omitted = _project_section(section, section_value)
        omitted += section_omitted
        if projected_section is not None:
            projected[section] = projected_section
    return projected, omitted


def project_stored_chat_preset(row: Mapping[str, JSONValue]) -> ChatPresetProjectedRecord:
    preset_id, name, revision, created_at_ms, modified_at_ms = _project_metadata(row)
    sections, omitted_settings_count = _project_sections(_decode_sections(row))
    return {
        "id": preset_id,
        "name": name,
        "sections": sections,
        "revision": revision,
        "created_at_ms": created_at_ms,
        "modified_at_ms": modified_at_ms,
        "omitted_settings_count": omitted_settings_count,
        "applicable": bool(sections),
    }
