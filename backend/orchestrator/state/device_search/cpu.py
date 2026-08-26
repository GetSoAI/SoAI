"""SoAI - CPU device search candidates [backend/orchestrator/state/device_search/cpu.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from orchestrator.state.device_search.collector import (
    CandidateCollector,
    device_terms,
    resolve_device_identifier,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("collect_cpu_candidates",)


def collect_cpu_candidates(hardware_snapshot: JSONDict, collector: CandidateCollector) -> None:
    cpu_list = hardware_snapshot.get("cpu") or []
    for cpu in cpu_list if isinstance(cpu_list, list) else []:
        if not isinstance(cpu, dict):
            continue
        device_id = resolve_device_identifier(cpu.get("device_id"), cpu.get("name"))
        if device_id is None:
            continue
        cpu_name = cpu.get("name")
        name = (str(cpu_name) if cpu_name is not None else "CPU").strip()
        terms = device_terms("cpu", "processor", cpu.get("vendor"), cpu.get("model"))
        cpu_metadata = {key: val for key, val in cpu.items() if key != "name"}
        collector.add_candidate(
            device_type="CPU",
            identifier=device_id,
            name=name,
            search_terms=terms,
            metadata=cpu_metadata,
        )
