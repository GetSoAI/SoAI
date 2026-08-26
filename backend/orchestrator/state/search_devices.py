"""SoAI - Device search candidate extraction [backend/orchestrator/state/search_devices.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.types.json import JSONDict
from orchestrator.state.device_search.collector import (
    CandidateCollector,
    resolve_device_identifier,
)
from orchestrator.state.device_search.cpu import collect_cpu_candidates
from orchestrator.state.device_search.disk import collect_disk_candidates
from orchestrator.state.device_search.gpu import collect_gpu_candidates
from orchestrator.state.device_search.network import collect_network_candidates

__all__ = (
    "resolve_device_identifier",
    "resolve_device_search_result",
    "resolve_device_search_text",
    "search_devices_candidates",
)


def _search_devices_candidates(hardware_snapshot: JSONDict) -> list[JSONDict]:
    collector = CandidateCollector()
    collect_cpu_candidates(hardware_snapshot, collector)
    collect_gpu_candidates(hardware_snapshot, collector)
    collect_disk_candidates(hardware_snapshot, collector)
    collect_network_candidates(hardware_snapshot, collector)
    return collector.candidates


def resolve_device_search_text(data: JSONDict) -> str:
    search_terms = data.get("_search_terms", []) or []
    return (
        " ".join([item for item in search_terms if isinstance(item, str)])
        if isinstance(search_terms, list)
        else ""
    )


def resolve_device_search_result(data: JSONDict) -> JSONDict:
    return {
        field_key: field_value
        for field_key, field_value in data.items()
        if field_key != "_search_terms"
    }


def search_devices_candidates(hardware_snapshot: JSONDict | None) -> list[JSONDict]:
    if hardware_snapshot is None:
        return []
    return _search_devices_candidates(hardware_snapshot)
