"""SoAI - Plugin SDK accelerator inventory snapshot contract [backend/plugin_sdk/contracts/accelerator_inventory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types.json import JSONDict, is_json_dict

if TYPE_CHECKING:
    from plugin_sdk.protocols import AcceleratorInventoryProviderProtocol

__all__ = ("snapshot_accelerator_inventory",)


async def snapshot_accelerator_inventory(
    provider: AcceleratorInventoryProviderProtocol | None,
) -> JSONDict | None:
    if provider is None:
        return None
    snapshot = await provider.get_system_info(components=["gpu"], cache=False)
    return dict(snapshot) if is_json_dict(snapshot) else None
