"""SoAI - Device search candidate collector [backend/orchestrator/state/device_search/collector.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.types.json import JSONDict, JSONValue

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = (
    "CandidateCollector",
    "device_terms",
    "resolve_device_identifier",
)

_CANDIDATE_CONTRACT_KEYS: frozenset[str] = frozenset(
    ("type", "name", "id", "device_id", "identifier", "component"),
)


def device_terms(*terms: JSONValue | None) -> list[JSONValue]:
    return [term for term in terms if term not in (None, "")]


def resolve_device_identifier(*candidates: JSONValue | None) -> JSONValue | None:
    for candidate in candidates:
        if candidate not in (None, ""):
            return candidate
    return None


@dataclass(slots=True)
class CandidateCollector:
    candidates: list[JSONDict] = field(default_factory=list[JSONDict])
    _seen: set[tuple[str, str]] = field(default_factory=set[tuple[str, str]])

    def add_candidate(
        self,
        *,
        device_type: str,
        identifier: JSONValue | None,
        name: str,
        search_terms: Iterable[JSONValue] | None = None,
        metadata: Mapping[str, JSONValue] | None = None,
    ) -> None:
        resolved_name = name.strip()
        if not resolved_name or identifier is None:
            return
        resolved_id = str(identifier).strip()
        if not resolved_id:
            return
        seen_key = (device_type, resolved_id)
        if seen_key in self._seen:
            return
        candidate: JSONDict = {
            "type": device_type,
            "name": resolved_name,
            "id": resolved_id,
            "device_id": resolved_id,
            "identifier": resolved_id,
        }
        normalized_device_type = device_type.upper()
        if normalized_device_type == "CPU":
            candidate["component"] = "cpu"
        elif normalized_device_type == "GPU":
            candidate["component"] = "gpu"
        elif normalized_device_type == "VOLUME":
            candidate["component"] = "disk"
        elif normalized_device_type == "NETWORK":
            candidate["component"] = "network"
        if metadata:
            candidate.update(
                {
                    metadata_key: (
                        metadata_value
                        if isinstance(metadata_value, str | int | float | bool | list | dict)
                        or metadata_value is None
                        else str(metadata_value)
                    )
                    for metadata_key, metadata_value in metadata.items()
                    if metadata_value is not None and metadata_key not in _CANDIDATE_CONTRACT_KEYS
                },
            )
        filtered_terms = device_terms(*(search_terms or []))
        search_values: list[JSONValue] = [resolved_name]
        search_values.extend(str(term) for term in filtered_terms)
        candidate["_search_terms"] = search_values
        self.candidates.append(candidate)
        self._seen.add(seen_key)
