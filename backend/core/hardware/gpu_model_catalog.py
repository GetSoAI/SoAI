"""SoAI - GPU model identity catalog loader [backend/core/hardware/gpu_model_catalog.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from typing import TYPE_CHECKING

from core.hardware.gpu_identity_normalization import normalize_identity_name, normalize_model_key
from core.serialization.json_parsing import (
    StrictJSONDuplicateKeyError,
    StrictJSONNonFiniteError,
    parse_strict_json,
)

__all__ = (
    "GpuModelCatalogEntry",
    "catalog_entries",
    "resolve_catalog_model",
    "resolve_catalog_model_name",
    "resolve_catalog_submission_identity",
)

_CATALOG_FILE = "gpu_model_catalog.json"
_UNKNOWN_VENDOR_KEY = "unknown"
_CONFIGURATION_ANNOTATION_PATTERN_TEXT = (
    r"\s*(?:\(\s*(?:\d+(?:\.\d+)?\s*[GMT]i?B|nvgpu|Panfrost|Panthor)\s*\)"
    r"|\bFamily|\bM[CP]\d+|\br\d+p\d+)\s*$"
)
_TRADEMARK_PATTERN_TEXT = r"\(\s*(?:r|tm)\s*\)|[®™]"

if TYPE_CHECKING:
    from core.types.json import JSONValue


@dataclass(frozen=True, slots=True)
class GpuModelCatalogEntry:
    model_key: str
    name: str
    vendor: str
    aliases: tuple[str, ...]
    vendor_aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GpuCatalogIdentityResolution:
    model: GpuModelCatalogEntry | None
    requires_review: bool


@cache
def _catalog_data() -> tuple[tuple[GpuModelCatalogEntry, ...], dict[str, tuple[str, ...]]]:
    try:
        raw_text = files("core.hardware").joinpath(_CATALOG_FILE).read_text(encoding="utf-8")
        parsed = _parse_catalog_text(raw_text)
    except (OSError, SyntaxError, ValueError) as exception:
        raise ValueError("SoAI Bench GPU model catalog cannot be loaded.") from exception
    document = _require_mapping(parsed, "catalog")
    if set(document) != {"schema_version", "vendor_aliases", "models"}:
        raise ValueError("SoAI Bench GPU model catalog fields are invalid.")
    schema_version = document.get("schema_version")
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version != 1
    ):
        raise ValueError("SoAI Bench GPU model catalog schema is unsupported.")
    vendor_aliases = _load_vendor_aliases(document.get("vendor_aliases"))
    entries = _load_models(document.get("models"), vendor_aliases)
    return entries, vendor_aliases


def catalog_entries() -> tuple[GpuModelCatalogEntry, ...]:
    return _catalog_data()[0]


def resolve_catalog_model(
    gpu_name: str | None,
    gpu_model_key: str | None,
    vendor: str | None,
) -> GpuModelCatalogEntry | None:
    name_key = _catalog_match_key(gpu_name or "")
    model_key = _catalog_match_key(gpu_model_key or "")
    vendor_key = _catalog_match_key(vendor or "")
    if vendor_key == _UNKNOWN_VENDOR_KEY:
        vendor_key = ""
    matches: list[GpuModelCatalogEntry] = []
    for entry in catalog_entries():
        if _entry_matches_identity(entry, name_key, model_key, vendor_key):
            matches.append(entry)
    return matches[0] if len(matches) == 1 else None


def resolve_catalog_model_name(
    gpu_name: str | None,
    vendor: str | None,
) -> GpuModelCatalogEntry | None:
    exact = resolve_catalog_model(gpu_name, None, vendor)
    if exact is not None or gpu_name is None:
        return exact
    bracket_matches = _bracket_catalog_models(gpu_name, vendor)
    if bracket_matches:
        return next(iter(bracket_matches)) if len(bracket_matches) == 1 else None
    model_name = _without_configuration_annotations(gpu_name)
    if model_name == gpu_name or not _catalog_match_key(model_name):
        return None
    return resolve_catalog_model(model_name, None, vendor)


def _without_configuration_annotations(gpu_name: str) -> str:
    model_name = gpu_name
    while (
        stripped := re.sub(
            _CONFIGURATION_ANNOTATION_PATTERN_TEXT, "", model_name, flags=re.IGNORECASE
        )
    ) != model_name:
        model_name = stripped
    return model_name


def _bracket_catalog_models(gpu_name: str, vendor: str | None) -> set[GpuModelCatalogEntry]:
    return {
        model
        for bracket_name in re.findall(r"\[([^\[\]]+)\]", gpu_name)
        if (model := resolve_catalog_model(bracket_name, None, vendor)) is not None
    }


def resolve_catalog_submission_identity(
    gpu_name: str | None,
    gpu_model_key: str | None,
    vendor: str | None,
) -> GpuCatalogIdentityResolution:
    exact = resolve_catalog_model(gpu_name, gpu_model_key, vendor)
    if exact is not None:
        return GpuCatalogIdentityResolution(exact, False)
    if gpu_name is not None and len(_bracket_catalog_models(gpu_name, None)) > 1:
        return GpuCatalogIdentityResolution(None, True)
    named = resolve_catalog_model_name(gpu_name, vendor) if gpu_name else None
    keyed = resolve_catalog_model(None, gpu_model_key, vendor) if gpu_model_key else None
    named_without_vendor = resolve_catalog_model_name(gpu_name, None) if gpu_name else None
    keyed_without_vendor = (
        resolve_catalog_model(None, gpu_model_key, None) if gpu_model_key else None
    )
    if named is not None and keyed is not None and named != keyed:
        return GpuCatalogIdentityResolution(None, True)
    if named is not None and keyed_without_vendor in {None, named}:
        return GpuCatalogIdentityResolution(named, False)
    if keyed is not None and named_without_vendor in {None, keyed}:
        return GpuCatalogIdentityResolution(keyed, False)
    return GpuCatalogIdentityResolution(
        None,
        named_without_vendor is not None or keyed_without_vendor is not None,
    )


def _entry_matches_identity(
    entry: GpuModelCatalogEntry,
    name_key: str,
    model_key: str,
    vendor_key: str,
) -> bool:
    candidate_keys = _entry_candidate_keys(entry)
    name_matches = not name_key or name_key in candidate_keys
    model_matches = not model_key or model_key in candidate_keys
    vendor_matches = not vendor_key or vendor_key in entry.vendor_aliases
    return name_matches and model_matches and vendor_matches


@cache
def _entry_candidate_keys(entry: GpuModelCatalogEntry) -> frozenset[str]:
    return frozenset(
        _model_candidate_keys(entry.vendor, (entry.model_key, entry.name, *entry.aliases))
    )


def _model_candidate_keys(vendor: str, names: tuple[str, ...]) -> tuple[str, ...]:
    vendor_key = _catalog_match_key(vendor)
    keys = _unique_normalized(names)
    vendor_qualified = (
        f"{vendor_key}{key}"
        for key in keys
        if not key.startswith(vendor_key) and f"{vendor_key}{key}" not in keys
    )
    return (*keys, *vendor_qualified)


def _catalog_match_key(value: str) -> str:
    return normalize_identity_name(re.sub(_TRADEMARK_PATTERN_TEXT, "", value, flags=re.IGNORECASE))


def _load_vendor_aliases(value: JSONValue) -> dict[str, tuple[str, ...]]:
    records = _require_list(value, "vendor_aliases")
    result: dict[str, tuple[str, ...]] = {}
    vendor_candidates: set[str] = set()
    for record_value in records:
        record = _require_mapping(record_value, "vendor alias record")
        if set(record) != {"vendor_key", "canonical_vendor", "aliases", "pci_vendor_id"}:
            raise ValueError("SoAI Bench GPU vendor catalog fields are invalid.")
        vendor_key = _required_text(record, "vendor_key")
        canonical_vendor = _required_text(record, "canonical_vendor")
        aliases = _required_text_list(record, "aliases")
        pci_vendor_id = _required_text(record, "pci_vendor_id")
        normalized_candidates = _unique_normalized(
            (vendor_key, canonical_vendor, *aliases, pci_vendor_id),
        )
        if not _is_pci_id(pci_vendor_id) or any(
            candidate in vendor_candidates for candidate in normalized_candidates
        ):
            raise ValueError("SoAI Bench GPU vendor catalog is invalid.")
        vendor_candidates.update(normalized_candidates)
        result[canonical_vendor] = normalized_candidates
    if not {"NVIDIA", "AMD", "Intel"}.issubset(result):
        raise ValueError("SoAI Bench GPU vendor catalog is incomplete.")
    return result


def _load_models(
    value: JSONValue,
    vendor_aliases: dict[str, tuple[str, ...]],
) -> tuple[GpuModelCatalogEntry, ...]:
    records = _require_list(value, "models")
    entries: list[GpuModelCatalogEntry] = []
    model_keys: set[str] = set()
    candidates: set[tuple[str, str]] = set()
    for record_value in records:
        record = _require_mapping(record_value, "GPU model record")
        if set(record) != {"model_key", "name", "vendor", "aliases"}:
            raise ValueError("SoAI Bench GPU model catalog fields are invalid.")
        model_key = _required_text(record, "model_key")
        name = _required_text(record, "name")
        vendor = _required_text(record, "vendor")
        aliases = _required_text_list(record, "aliases")
        if (
            normalize_model_key(model_key) != model_key
            or model_key in model_keys
            or vendor not in vendor_aliases
            or not aliases
        ):
            raise ValueError("SoAI Bench GPU model catalog is invalid.")
        model_keys.add(model_key)
        all_names = _model_candidate_keys(vendor, (model_key, name, *aliases))
        vendor_names = vendor_aliases[vendor]
        for candidate in all_names:
            candidate_pair = (vendor, candidate)
            if candidate_pair in candidates:
                raise ValueError("SoAI Bench GPU model aliases are ambiguous.")
            candidates.add(candidate_pair)
        entries.append(GpuModelCatalogEntry(model_key, name, vendor, tuple(aliases), vendor_names))
    if not entries:
        raise ValueError("SoAI Bench GPU model catalog is empty.")
    return tuple(entries)


def _require_mapping(value: JSONValue, label: str) -> dict[str, JSONValue]:
    if not isinstance(value, dict):
        raise ValueError(f"SoAI Bench {label} must be an object.")
    return value


def _require_list(value: JSONValue, label: str) -> list[JSONValue]:
    if not isinstance(value, list):
        raise ValueError(f"SoAI Bench {label} must be a list.")
    return value


def _required_text(record: dict[str, JSONValue], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("SoAI Bench GPU model catalog contains invalid text.")
    return value


def _required_text_list(record: dict[str, JSONValue], field: str) -> list[str]:
    values = _require_list(record.get(field), field)
    result: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("SoAI Bench GPU model catalog contains invalid aliases.")
        result.append(value)
    return result


def _unique_normalized(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = _catalog_match_key(value)
        if not key:
            raise ValueError("SoAI Bench GPU model catalog contains an empty identifier.")
        if key not in seen:
            normalized.append(key)
            seen.add(key)
    return tuple(normalized)


def _is_pci_id(value: str) -> bool:
    return len(value) == 4 and all(character in "0123456789abcdefABCDEF" for character in value)


def _parse_catalog_text(raw_text: str) -> JSONValue:
    try:
        return parse_strict_json(
            raw_text,
            field="SoAI Bench GPU model catalog",
            max_depth=16,
            reject_duplicate_keys=True,
        )
    except StrictJSONDuplicateKeyError as exception:
        raise ValueError("SoAI Bench GPU model catalog contains duplicate fields.") from exception
    except StrictJSONNonFiniteError as exception:
        raise ValueError("SoAI Bench GPU model catalog contains a nonfinite number.") from exception
