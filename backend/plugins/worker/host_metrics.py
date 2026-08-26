"""SoAI - Plugin worker host metrics dispatch [backend/plugins/worker/host_metrics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.metrics.protocols import MetricsManagerProtocol
from core.types.json import JSONDict
from plugins.worker.host_payloads import enforce_record_plugin_scope
from plugins.worker.payload_fields import (
    read_int_field,
    read_number_field,
    read_required_named_str_field,
    read_scalar_field,
    read_str_list_field,
)

__all__ = ("record_worker_metrics_batch",)

HOST_FIELD_LABEL = "Worker host request field"


def record_worker_metrics_batch(
    manager_metrics: MetricsManagerProtocol,
    *,
    resolved_plugin_name: str,
    records: list[JSONDict],
) -> None:
    for record in records:
        operation = read_required_named_str_field(record, "operation", label=HOST_FIELD_LABEL)
        if operation == "increment_counter":
            keys = read_str_list_field(record, "keys", label=HOST_FIELD_LABEL)
            manager_metrics.increment_counter(
                *keys,
                value=read_int_field(record, "value", label=HOST_FIELD_LABEL, default=1),
            )
        elif operation == "set_gauge":
            keys = read_str_list_field(record, "keys", label=HOST_FIELD_LABEL)
            manager_metrics.set_gauge(
                *keys,
                value=read_number_field(record, "value", label=HOST_FIELD_LABEL),
            )
        elif operation == "record_timing":
            keys = read_str_list_field(record, "keys", label=HOST_FIELD_LABEL)
            manager_metrics.record_timing(
                *keys,
                duration_ms=read_number_field(record, "value", label=HOST_FIELD_LABEL),
            )
        elif operation == "record_unique":
            keys = read_str_list_field(record, "keys", label=HOST_FIELD_LABEL)
            manager_metrics.record_unique(
                *keys,
                item=read_scalar_field(record, "item", label=HOST_FIELD_LABEL),
            )
        elif operation == "record_tokens_for_billing":
            enforce_record_plugin_scope(record, resolved_plugin_name, key="plugin")
            manager_metrics.record_tokens_for_billing(
                resolved_plugin_name,
                read_required_named_str_field(record, "model_id", label=HOST_FIELD_LABEL),
                read_required_named_str_field(record, "client_id", label=HOST_FIELD_LABEL),
                read_int_field(record, "tokens", label=HOST_FIELD_LABEL, default=0),
            )
        elif operation == "record_completion_tokens":
            enforce_record_plugin_scope(record, resolved_plugin_name, key="plugin")
            manager_metrics.record_completion_tokens(
                resolved_plugin_name,
                read_int_field(record, "tokens", label=HOST_FIELD_LABEL, default=0),
            )
        elif operation == "update_download_speed_metrics":
            manager_metrics.update_download_speed_metrics(
                read_number_field(record, "bytes_per_second", label=HOST_FIELD_LABEL),
                source=read_required_named_str_field(record, "source", label=HOST_FIELD_LABEL),
            )
        elif operation == "increment_genesis_request":
            manager_metrics.increment_genesis_request()
        elif operation == "purge_plugin_metrics":
            enforce_record_plugin_scope(record, resolved_plugin_name, key="plugin_name")
            manager_metrics.purge_plugin_metrics(resolved_plugin_name)
        else:
            raise ValidationError(f"Unsupported worker metrics operation '{operation}'.")
