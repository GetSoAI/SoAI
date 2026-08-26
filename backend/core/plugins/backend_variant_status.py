"""SoAI - Installed backend variant reads from plugin status payloads [backend/core/plugins/backend_variant_status.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.plugins.backend_variant_ids import normalize_backend_variant_id
from core.types.json import JSONDict

__all__ = (
    "read_installed_backend_variant_id",
    "status_reports_installed_backend",
)

_INSTALLED_STATUS_VALUES = frozenset({"installed", "ok", "running"})


def status_reports_installed_backend(status_payload: JSONDict) -> bool:
    installed_value = status_payload.get("installed")
    if isinstance(installed_value, bool):
        return installed_value
    if "installed" in status_payload:
        return False
    status_value = status_payload.get("status")
    if isinstance(status_value, str):
        return status_value.strip().lower() in _INSTALLED_STATUS_VALUES
    return False


def read_installed_backend_variant_id(status_payload: JSONDict) -> str | None:
    if not status_reports_installed_backend(status_payload):
        return None
    return normalize_backend_variant_id(status_payload.get("backend_variant_id"))
