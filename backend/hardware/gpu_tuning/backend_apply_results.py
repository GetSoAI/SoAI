"""SoAI - GPU tuning backend apply result aggregation [backend/hardware/gpu_tuning/backend_apply_results.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.types.json import is_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "gpu_apply_result_changed",
    "merge_backend_apply_result",
)


def gpu_apply_result_changed(result: Mapping[str, JSONValue]) -> bool:
    return _gpu_apply_mapping_changed(result, depth=0)


def _gpu_apply_mapping_changed(result: Mapping[str, JSONValue], *, depth: int) -> bool:
    if result.get("changed") is True:
        return True
    gpus_value = result.get("gpus")
    if isinstance(gpus_value, Mapping):
        for entry in gpus_value.values():
            if isinstance(entry, Mapping) and entry.get("changed") is True:
                return True
    if depth >= 2:
        return False
    for nested_key in ("details", "payload", "result"):
        nested_value = result.get(nested_key)
        if is_json_dict(nested_value) and _gpu_apply_mapping_changed(
            nested_value,
            depth=depth + 1,
        ):
            return True
    return False


def merge_backend_apply_result(
    apply_result: JSONDict,
    backend_result: JSONDict,
) -> tuple[bool, bool]:
    apply_messages = apply_result.get("messages")
    apply_errors = apply_result.get("errors")
    if not isinstance(apply_messages, list) or not isinstance(apply_errors, list):
        return True, False
    backend_messages = backend_result.get("messages")
    backend_changed = backend_result.get("changed") is True
    if isinstance(backend_messages, list):
        apply_messages.extend(str(message) for message in backend_messages)
        backend_changed = backend_changed or bool(backend_messages)
    backend_errors = backend_result.get("errors")
    if isinstance(backend_errors, list):
        apply_errors.extend(str(error) for error in backend_errors)
        return bool(backend_errors), backend_changed
    apply_errors.append("GPU backend result payload is invalid.")
    return True, backend_changed
