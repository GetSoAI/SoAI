"""SoAI - Plugin worker host router payload helpers [backend/plugins/worker/host_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict
from plugins.worker.payload_fields import read_required_str_field

__all__ = (
    "enforce_plugin_scope",
    "enforce_record_plugin_scope",
)


def enforce_plugin_scope(payload: JSONDict, resolved_plugin_name: str) -> None:
    candidate = read_required_str_field(
        payload,
        "plugin_name",
        missing_message="Worker host request field 'plugin_name' is required.",
        type_message="Worker host request field 'plugin_name' must be a string.",
        empty_message="Worker host request field 'plugin_name' cannot be blank.",
    )
    if candidate != resolved_plugin_name:
        raise ValidationError("Worker host request cannot target a different plugin.")


def enforce_record_plugin_scope(
    payload: JSONDict,
    resolved_plugin_name: str,
    *,
    key: str,
) -> None:
    candidate = read_required_str_field(
        payload,
        key,
        missing_message=f"Worker host metrics field '{key}' is required.",
        type_message=f"Worker host metrics field '{key}' must be a string.",
        empty_message=f"Worker host metrics field '{key}' cannot be blank.",
    )
    if candidate != resolved_plugin_name:
        raise ValidationError("Worker host metrics cannot target a different plugin.")
