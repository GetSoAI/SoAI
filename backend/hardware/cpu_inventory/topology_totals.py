"""SoAI - CPU inventory aggregate count authority [backend/hardware/cpu_inventory/topology_totals.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.validation.numbers import coerce_int_from_json

if TYPE_CHECKING:
    from core.types.json import JSONDict


__all__ = (
    "total_cpu_count",
    "KernelPackageCounts",
    "kernel_package_counts",
)


def total_cpu_count(cpus: list[JSONDict], field: str) -> int | None:
    if not cpus:
        return None
    aggregate_records = [cpu for cpu in cpus if cpu.get("topology_scope") == "aggregate"]
    if aggregate_records and len(cpus) != 1:
        return None
    socket_ids: set[int] = set()
    observed_cpu_ids: set[int] = set()
    total = 0
    for cpu in cpus:
        if cpu.get("topology_status") in ("conflict", "incomplete"):
            return None
        online_ids = cpu.get("online_cpu_ids")
        if isinstance(online_ids, list):
            for identity in online_ids:
                if not isinstance(identity, int) or isinstance(identity, bool) or identity < 0:
                    return None
                if identity in observed_cpu_ids:
                    return None
                observed_cpu_ids.add(identity)
        count = coerce_int_from_json(cpu.get(field), default=None)
        if count is None or count <= 0:
            return None
        socket_id = cpu.get("socket_id")
        if isinstance(socket_id, int) and not isinstance(socket_id, bool):
            if socket_id in socket_ids:
                return None
            socket_ids.add(socket_id)
        total += count
    return total


@dataclass(frozen=True, slots=True)
class KernelPackageCounts:
    package_id: int
    physical_cores: int
    logical_cores: int
    online_cpu_ids: tuple[int, ...]


def kernel_package_counts(relationships: JSONDict) -> list[KernelPackageCounts]:
    if (
        relationships.get("relationship_status") != "available"
        or relationships.get("relationship_scope") != "present"
    ):
        return []
    rows = relationships.get("cpu_relationships")
    if not isinstance(rows, list):
        return []
    cores_by_package: dict[int, set[int]] = {}
    cpus_by_package: dict[int, set[int]] = {}
    for row in rows:
        if not isinstance(row, dict):
            return []
        package_id = coerce_int_from_json(row.get("kernel_package_id"))
        core_id = coerce_int_from_json(row.get("core_id"))
        cpu_id = coerce_int_from_json(row.get("cpu_id"))
        if package_id is None or core_id is None or cpu_id is None:
            return []
        if package_id not in cores_by_package:
            cores_by_package[package_id] = set()
        cores_by_package[package_id].add(core_id)
        if package_id not in cpus_by_package:
            cpus_by_package[package_id] = set()
        cpus_by_package[package_id].add(cpu_id)
    return [
        KernelPackageCounts(
            package_id,
            len(cores_by_package[package_id]),
            len(cpus_by_package[package_id]),
            tuple(sorted(cpus_by_package[package_id])),
        )
        for package_id in sorted(cores_by_package)
    ]
