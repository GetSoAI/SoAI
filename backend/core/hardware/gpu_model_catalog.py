"""SoAI - GPU model identity catalog loader [backend/core/hardware/gpu_model_catalog.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

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
)

_CATALOG_FILE = "gpu_model_catalog.json"

if TYPE_CHECKING:
    from core.types.json import JSONValue


@dataclass(frozen=True, slots=True)
class GpuModelCatalogEntry:
    model_key: str
    name: str
    vendor: str
    aliases: tuple[str, ...]
    vendor_aliases: tuple[str, ...]


@cache
def _catalog_data() -> tuple[tuple[GpuModelCatalogEntry, ...], dict[str, tuple[str, ...]]]:
    try:
        raw_text = files("core.hardware").joinpath(_CATALOG_FILE).read_text(encoding="utf-8")
        parsed = _parse_catalog_text(raw_text)
    except (OSError, SyntaxError, ValueError) as exception:
        raise ValueError("SoAIBench GPU model catalog cannot be loaded.") from exception
    document = _require_mapping(parsed, "catalog")
    if set(document) != {"schema_version", "vendor_aliases", "models"}:
        raise ValueError("SoAIBench GPU model catalog fields are invalid.")
    schema_version = document.get("schema_version")
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version != 1
    ):
        raise ValueError("SoAIBench GPU model catalog schema is unsupported.")
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
    name_key = normalize_identity_name(gpu_name or "")
    model_key = normalize_identity_name(gpu_model_key or "")
    vendor_key = normalize_identity_name(vendor or "")
    matches: list[GpuModelCatalogEntry] = []
    for entry in catalog_entries():
        if _entry_matches_identity(entry, name_key, model_key, vendor_key):
            matches.append(entry)
    return matches[0] if len(matches) == 1 else None


def _entry_matches_identity(
    entry: GpuModelCatalogEntry,
    name_key: str,
    model_key: str,
    vendor_key: str,
) -> bool:
    candidate_keys = {
        normalize_identity_name(entry.model_key),
        normalize_identity_name(entry.name),
        *(normalize_identity_name(alias) for alias in entry.aliases),
    }
    accepted_vendors = {normalize_identity_name(alias) for alias in entry.vendor_aliases}
    name_matches = not name_key or name_key in candidate_keys
    model_matches = not model_key or model_key in candidate_keys
    vendor_matches = not vendor_key or vendor_key in accepted_vendors
    return name_matches and model_matches and vendor_matches


def _load_vendor_aliases(value: JSONValue) -> dict[str, tuple[str, ...]]:
    records = _require_list(value, "vendor_aliases")
    result: dict[str, tuple[str, ...]] = {}
    vendor_candidates: set[str] = set()
    for record_value in records:
        record = _require_mapping(record_value, "vendor alias record")
        if set(record) != {"vendor_key", "canonical_vendor", "aliases", "pci_vendor_id"}:
            raise ValueError("SoAIBench GPU vendor catalog fields are invalid.")
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
            raise ValueError("SoAIBench GPU vendor catalog is invalid.")
        vendor_candidates.update(normalized_candidates)
        result[canonical_vendor] = normalized_candidates
    if set(result) != {"NVIDIA", "AMD", "Intel"}:
        raise ValueError("SoAIBench GPU vendor catalog is incomplete.")
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
            raise ValueError("SoAIBench GPU model catalog fields are invalid.")
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
            raise ValueError("SoAIBench GPU model catalog is invalid.")
        model_keys.add(model_key)
        all_names = _unique_normalized((model_key, name, *aliases))
        vendor_names = vendor_aliases[vendor]
        for candidate in all_names:
            candidate_pair = (vendor, candidate)
            if candidate_pair in candidates:
                raise ValueError("SoAIBench GPU model aliases are ambiguous.")
            candidates.add(candidate_pair)
        entries.append(GpuModelCatalogEntry(model_key, name, vendor, tuple(aliases), vendor_names))
    if not entries:
        raise ValueError("SoAIBench GPU model catalog is empty.")
    return tuple(entries)


def _require_mapping(value: JSONValue, label: str) -> dict[str, JSONValue]:
    if not isinstance(value, dict):
        raise ValueError(f"SoAIBench {label} must be an object.")
    return value


def _require_list(value: JSONValue, label: str) -> list[JSONValue]:
    if not isinstance(value, list):
        raise ValueError(f"SoAIBench {label} must be a list.")
    return value


def _required_text(record: dict[str, JSONValue], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("SoAIBench GPU model catalog contains invalid text.")
    return value


def _required_text_list(record: dict[str, JSONValue], field: str) -> list[str]:
    values = _require_list(record.get(field), field)
    result: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("SoAIBench GPU model catalog contains invalid aliases.")
        result.append(value)
    return result


def _unique_normalized(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = normalize_identity_name(value)
        if not key:
            raise ValueError("SoAIBench GPU model catalog contains an empty identifier.")
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
            field="SoAIBench GPU model catalog",
            max_depth=16,
            reject_duplicate_keys=True,
        )
    except StrictJSONDuplicateKeyError as exception:
        raise ValueError("SoAIBench GPU model catalog contains duplicate fields.") from exception
    except StrictJSONNonFiniteError as exception:
        raise ValueError("SoAIBench GPU model catalog contains a nonfinite number.") from exception
