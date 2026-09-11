"""SoAI - Canonical plugin manifest reader [backend/plugins/manifest/reader.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import NotFoundError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from plugins.manifest.ast_extraction import extract_plugin_manifest_from_disk
from plugins.package_audit import audit_plugin_package

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from plugins.package_audit import PluginPackageAudit
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = (
    "PLUGIN_MANIFEST_READ_EXCEPTIONS",
    "read_plugin_manifest_from_disk",
    "read_plugin_manifests_from_disk",
)

LOGGER_NAME = "SoAI.plugins.manifest.reader"
OPERATION = "plugins.manifest.reader.read_plugin_manifests_from_disk"

PLUGIN_MANIFEST_READ_EXCEPTIONS = RECOVERABLE_EXCEPTIONS + (
    NotFoundError,
    StateError,
    SyntaxError,
    OSError,
    ValueError,
)


def read_plugin_manifest_from_disk(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    *,
    enforce_safety_validation: bool = True,
    package_audit: PluginPackageAudit,
) -> JSONDict:
    manifest = extract_plugin_manifest_from_disk(
        manager,
        plugin_name,
        enforce_safety_validation=enforce_safety_validation,
        package_audit=package_audit,
    )
    return dict(manifest)


async def read_plugin_manifests_from_disk(
    manager: PluginManagerRuntimeProtocol,
    plugin_names: list[str],
    *,
    enforce_safety_validation: bool = True,
    package_audits: dict[str, PluginPackageAudit] | None = None,
    concurrency_limit: int = 1,
) -> dict[str, JSONDict]:
    logger = get_logger(LOGGER_NAME)
    manifests: dict[str, JSONDict] = {}
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    for plugin_name in plugin_names:
        queue.put_nowait(plugin_name)
    worker_count = min(max(1, concurrency_limit), len(plugin_names))
    for _index in range(worker_count):
        queue.put_nowait(None)

    async def worker() -> None:
        while True:
            plugin_name = await queue.get()
            if plugin_name is None:
                return
            await read_one(plugin_name)

    async def read_one(plugin_name: str) -> None:
        try:
            package_audit = package_audits.get(plugin_name) if package_audits is not None else None
            if package_audit is None:
                package_audit = await audit_plugin_package(
                    manager,
                    plugin_name,
                    enforce_import_scan=enforce_safety_validation,
                    enforce_hash_policy=False,
                )
            manifest = await asyncio.to_thread(
                read_plugin_manifest_from_disk,
                manager,
                plugin_name,
                enforce_safety_validation=enforce_safety_validation,
                package_audit=package_audit,
            )
            manifests[plugin_name] = manifest
        except PLUGIN_MANIFEST_READ_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message=f"Could not inspect manifest for plugin '{plugin_name}'",
                operation=OPERATION,
            )

    if worker_count == 0:
        return manifests
    worker_tasks = [worker() for _index in range(worker_count)]
    await asyncio.gather(*worker_tasks, return_exceptions=False)
    return manifests
