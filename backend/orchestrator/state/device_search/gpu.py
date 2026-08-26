"""SoAI - GPU device search candidates [backend/orchestrator/state/device_search/gpu.py]"""
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

__all__ = ("collect_gpu_candidates",)


def collect_gpu_candidates(hardware_snapshot: JSONDict, collector: CandidateCollector) -> None:
    gpu_list = hardware_snapshot.get("gpu") or []
    for gpu in gpu_list if isinstance(gpu_list, list) else []:
        if not isinstance(gpu, dict):
            continue
        device_id = resolve_device_identifier(
            gpu.get("device_id"),
            gpu.get("uuid"),
            gpu.get("name"),
        )
        if device_id is None:
            continue
        gpu_name = gpu.get("name")
        name = (str(gpu_name) if gpu_name is not None else "GPU").strip()
        terms = device_terms(
            "gpu",
            "graphics",
            gpu.get("uuid"),
            gpu.get("vendor"),
            gpu.get("architecture"),
            gpu.get("name"),
        )
        gpu_metadata = {key: val for key, val in gpu.items() if key != "name"}
        gpu_index = gpu.get("index")
        if isinstance(gpu_index, int) and gpu_index >= 0:
            gpu_metadata["gpu_index"] = gpu_index
        collector.add_candidate(
            device_type="GPU",
            identifier=device_id,
            name=name,
            search_terms=terms,
            metadata=gpu_metadata,
        )
