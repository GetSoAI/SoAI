"""SoAI - Network device search candidates [backend/orchestrator/state/device_search/network.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types.json import is_json_dict
from orchestrator.state.device_search.collector import (
    CandidateCollector,
    device_terms,
    resolve_device_identifier,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("collect_network_candidates",)

_IGNORED_NETWORK_PREFIXES: tuple[str, ...] = ("lo", "docker", "veth", "br", "virbr", "kube")


def collect_network_candidates(hardware_snapshot: JSONDict, collector: CandidateCollector) -> None:
    network_data = hardware_snapshot.get("network") or {}
    network_interfaces = (
        network_data.get("interfaces") if is_json_dict(network_data) else None
    ) or []
    interface_speeds = hardware_snapshot.get("network_speed") or {}
    for iface in network_interfaces if isinstance(network_interfaces, list) else []:
        if not is_json_dict(iface):
            continue
        name_val = iface.get("name")
        name = str(name_val) if name_val is not None else ""
        if not name or any(name.lower().startswith(prefix) for prefix in _IGNORED_NETWORK_PREFIXES):
            continue
        addresses_val = iface.get("addresses")
        addresses = addresses_val if isinstance(addresses_val, list) else []
        mac = iface.get("mac_address")
        speed_entry: JSONDict | None = None
        if is_json_dict(interface_speeds):
            speed_entry_value = interface_speeds.get(name)
            if is_json_dict(speed_entry_value):
                speed_entry = speed_entry_value
        address_terms = [addr.get("address") for addr in addresses if is_json_dict(addr)]
        network_terms = device_terms("network", "interface", "nic", mac, *address_terms)
        device_id = resolve_device_identifier(iface.get("device_id"), name)
        download_mbps = None
        upload_mbps = None
        if speed_entry is not None:
            download_mbps = speed_entry.get("download_mbps")
            upload_mbps = speed_entry.get("upload_mbps")
        collector.add_candidate(
            device_type="NETWORK",
            identifier=device_id,
            name=name,
            search_terms=network_terms,
            metadata={
                "mac_address": mac,
                "addresses": addresses,
                "download_mbps": download_mbps,
                "upload_mbps": upload_mbps,
            },
        )
