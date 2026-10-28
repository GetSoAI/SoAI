"""SoAI - Linux CPU topology and observed model-group interpretation [backend/hardware/cpu_inventory/linux_topology.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.filesystem.open_files import open_text
from core.validation.numbers import coerce_float_from_json, coerce_int_from_json

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "CPU_TOPOLOGY_FACT_FIELDS",
    "cpu_list_identities",
    "CpuMask",
    "read_cpu_mask",
    "read_online_core_relationships",
    "parse_linux_cpu_topology",
)

CPU_TOPOLOGY_FACT_FIELDS = frozenset(
    (
        "CPU(s)",
        "On-line CPU(s) list",
        "Socket(s)",
        "Core(s) per socket",
        "Core(s) per cluster",
        "Cluster(s)",
        "Thread(s) per core",
    )
)


def cpu_list_identities(value: str) -> list[int] | None:
    if not value.strip():
        return None
    identities: set[int] = set()
    for component in value.strip().split(","):
        if re.fullmatch(r"[0-9]+(?:-[0-9]+)?", component) is None:
            return None
        start_text, separator, end_text = component.partition("-")
        start = int(start_text)
        end = int(end_text) if separator else start
        if end < start or end - start > 1048576:
            return None
        members = set(range(start, end + 1))
        if identities.intersection(members):
            return None
        identities.update(members)
    return sorted(identities)


def _lscpu_fields(entries: list[JSONValue]) -> list[tuple[str, JSONValue]]:
    fields: list[tuple[str, JSONValue]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        field = entry.get("field")
        if isinstance(field, str):
            fields.append((field.strip().rstrip(":"), entry.get("data")))
        children = entry.get("children")
        if isinstance(children, list):
            fields.extend(_lscpu_fields(children))
    return fields


def _positive_count(value: JSONValue) -> int | None:
    count = coerce_int_from_json(value)
    return count if count is not None and count > 0 else None


def _frequency(value: JSONValue) -> float | None:
    if isinstance(value, str) and re.fullmatch(r"[0-9]+(?:[.,][0-9]+)?", value.strip()):
        value = value.strip().replace(",", ".")
    frequency = coerce_float_from_json(value, default=None)
    return frequency if frequency is not None and frequency >= 0 else None


@dataclass(frozen=True, slots=True)
class CpuMask:
    status: str
    identities: list[int] | None


def read_cpu_mask(name: str) -> CpuMask:
    try:
        with open_text(f"/sys/devices/system/cpu/{name}", encoding="utf-8") as file_handle:
            identities = cpu_list_identities(file_handle.read().strip())
            return CpuMask("available" if identities is not None else "malformed", identities)
    except OSError:
        return CpuMask("unavailable", None)


def read_online_core_relationships(
    online_cpus: list[int], observed_logical_count: int | None = None
) -> JSONDict:
    masks_before = {name: read_cpu_mask(name) for name in ("online", "present", "possible")}
    if any(mask.status == "malformed" for mask in masks_before.values()):
        return {"relationship_status": "conflict", "online_physical_cores": None}
    possible_before = masks_before["possible"].identities
    if possible_before is not None and not set(online_cpus).issubset(possible_before):
        return {"relationship_status": "conflict", "online_physical_cores": None}
    relationships: list[JSONValue] = []
    identities: set[tuple[int, int]] = set()
    for cpu_index in online_cpus:
        base = f"/sys/devices/system/cpu/cpu{cpu_index}/topology"
        try:
            values: dict[str, str] = {}
            for field in ("physical_package_id", "core_id", "thread_siblings_list"):
                with open_text(f"{base}/{field}", encoding="utf-8") as file_handle:
                    values[field] = file_handle.read().strip()
        except OSError:
            return {"relationship_status": "unavailable", "online_physical_cores": None}
        package_id = coerce_int_from_json(values["physical_package_id"])
        core_id = coerce_int_from_json(values["core_id"])
        siblings = cpu_list_identities(values["thread_siblings_list"])
        if package_id is None or core_id is None or siblings is None:
            return {"relationship_status": "conflict", "online_physical_cores": None}
        if package_id == -1:
            return {"relationship_status": "unavailable", "online_physical_cores": None}
        if package_id < 0 or core_id < 0 or cpu_index not in siblings:
            return {"relationship_status": "conflict", "online_physical_cores": None}
        if possible_before is not None and not set(siblings).issubset(possible_before):
            return {"relationship_status": "conflict", "online_physical_cores": None}
        identities.add((package_id, core_id))
        relationships.append(
            {
                "cpu_id": cpu_index,
                "kernel_package_id": package_id,
                "core_id": core_id,
                "thread_siblings": siblings,
            }
        )
    for relationship in relationships:
        if not isinstance(relationship, dict):
            continue
        siblings = relationship.get("thread_siblings")
        if not isinstance(siblings, list):
            continue
        for other in relationships:
            if not isinstance(other, dict):
                continue
            same_core = other.get("kernel_package_id") == relationship.get(
                "kernel_package_id"
            ) and other.get("core_id") == relationship.get("core_id")
            sibling_member = other.get("cpu_id") in siblings
            if same_core != sibling_member or (
                sibling_member and other.get("thread_siblings") != siblings
            ):
                return {"relationship_status": "conflict", "online_physical_cores": None}
    masks_after = {name: read_cpu_mask(name) for name in ("online", "present", "possible")}
    if any(mask.status == "malformed" for mask in masks_after.values()):
        return {"relationship_status": "conflict", "online_physical_cores": None}
    online_mask = masks_before["online"].identities
    present_mask = masks_before["present"].identities
    possible_mask = masks_before["possible"].identities
    stable = masks_before == masks_after and online_mask == online_cpus
    valid_membership = present_mask is None or set(online_cpus).issubset(present_mask)
    if possible_mask is not None and present_mask is not None:
        valid_membership = valid_membership and set(present_mask).issubset(possible_mask)
    complete_population = (
        online_cpus == present_mask
        if present_mask is not None
        else observed_logical_count == len(online_cpus)
    )
    return {
        "relationship_status": "available" if stable and valid_membership else "incomplete",
        "relationship_scope": (
            "present" if stable and valid_membership and complete_population else "online"
        ),
        "online_physical_cores": len(identities) if stable and valid_membership else None,
        "cpu_relationships": relationships,
        "present_cpu_ids": present_mask,
        "possible_cpu_capacity": len(possible_mask) if possible_mask is not None else None,
    }


def parse_linux_cpu_topology(payload: JSONDict) -> list[JSONDict]:
    entries = payload.get("lscpu")
    if not isinstance(entries, list):
        return []
    fields = _lscpu_fields(entries)
    global_fields: JSONDict = {}
    groups: list[JSONDict] = []
    conflicting_fields: set[str] = set()
    for field, value in fields:
        if field == "Model name":
            groups.append({field: value})
        else:
            target = groups[-1] if groups else global_fields
            if field in target and target[field] != value:
                conflicting_fields.add(field)
                target[field] = None
            elif field not in conflicting_fields:
                target[field] = value
    if not groups:
        groups = [global_fields.copy()]
    combined_groups = [{**global_fields, **group} for group in groups]
    first = combined_groups[0]
    online_value = global_fields.get("On-line CPU(s) list", first.get("On-line CPU(s) list"))
    online_cpus = cpu_list_identities(online_value) if isinstance(online_value, str) else None
    reported_count = _positive_count(global_fields.get("CPU(s)", first.get("CPU(s)")))
    package_count = _positive_count(first.get("Socket(s)")) if len(groups) == 1 else None
    physical_per_package = _positive_count(first.get("Core(s) per socket"))
    threads_per_core = _positive_count(first.get("Thread(s) per core"))
    homogeneous = (
        len(groups) == 1
        and package_count is not None
        and physical_per_package is not None
        and threads_per_core is not None
    )
    expected_logical = None
    if (
        package_count is not None
        and physical_per_package is not None
        and threads_per_core is not None
    ):
        expected_logical = package_count * physical_per_package * threads_per_core
    conflict = bool(conflicting_fields.intersection(CPU_TOPOLOGY_FACT_FIELDS)) or (
        expected_logical is not None
        and reported_count is not None
        and expected_logical != reported_count
    )
    records: list[JSONDict] = []
    if (
        homogeneous
        and not conflict
        and package_count is not None
        and physical_per_package is not None
        and threads_per_core is not None
    ):
        for socket_index in range(package_count):
            records.append(
                {
                    "socket_id": socket_index,
                    "topology_scope": "package",
                    "package_count": package_count,
                    "physical_cores": physical_per_package,
                    "logical_cores": physical_per_package * threads_per_core,
                    "name": first.get("Model name"),
                    "architecture": first.get("Architecture"),
                    "min_freq_mhz": _frequency(first.get("CPU min MHz")),
                    "max_freq_mhz": _frequency(first.get("CPU max MHz")),
                }
            )
    else:
        domains: list[JSONValue] = []
        for group in combined_groups:
            cores = _positive_count(group.get("Core(s) per socket")) or _positive_count(
                group.get("Core(s) per cluster")
            )
            threads = _positive_count(group.get("Thread(s) per core"))
            clusters = (
                _positive_count(group.get("Cluster(s)")) if "Core(s) per cluster" in group else 1
            )
            count = cores * clusters if cores is not None and clusters is not None else None
            domains.append(
                {
                    "name": group.get("Model name"),
                    "reported_cores": count,
                    "core_count_scope": "cluster" if "Core(s) per cluster" in group else "socket",
                    "reported_socket_count": _positive_count(group.get("Socket(s)")),
                    "threads_per_core": threads,
                    "min_freq_mhz": _frequency(group.get("CPU min MHz")),
                    "max_freq_mhz": _frequency(group.get("CPU max MHz")),
                }
            )
        logical_count = reported_count
        records.append(
            {
                "socket_id": None,
                "topology_scope": "aggregate",
                "package_count": package_count,
                "physical_cores": None,
                "logical_cores": logical_count,
                "name": " / ".join(
                    model_name
                    for group in combined_groups
                    for model_name in [group.get("Model name")]
                    if isinstance(model_name, str)
                ),
                "architecture": first.get("Architecture"),
                "min_freq_mhz": _frequency(first.get("CPU min MHz")) if len(groups) == 1 else None,
                "max_freq_mhz": _frequency(first.get("CPU max MHz")) if len(groups) == 1 else None,
                "model_groups": domains,
                "model_groups_scope": "system",
            }
        )
    for record in records:
        record["topology_status"] = "conflict" if conflict else "available"
        record["topology_conflicts"] = sorted(
            conflicting_fields.intersection(CPU_TOPOLOGY_FACT_FIELDS)
        )
        record["lscpu_field_conflicts"] = sorted(conflicting_fields)
        record["reported_logical_cores"] = reported_count
        record["online_logical_cores"] = (
            len(online_cpus) if online_cpus is not None and len(records) == 1 else None
        )
        record["online_cpu_ids"] = online_cpus if len(records) == 1 else None
        record["system_online_cpu_ids"] = online_cpus
        record["system_online_logical_cores"] = (
            len(online_cpus) if online_cpus is not None else None
        )
    return records
