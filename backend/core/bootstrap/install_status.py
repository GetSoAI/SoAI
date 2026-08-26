"""SoAI - Install progress status writer [backend/core/bootstrap/install_status.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

from core.bootstrap.launch_console import emit
from core.filesystem.atomic_writes import atomic_write_text_content
from core.meta.paths import join_data_abs
from core.serialization.json import (
    serialize_json_compact_stable_strict,
    serialize_json_pretty_sorted_strict,
)
from core.timing.formatting import utc_now, utc_now_log_format
from core.types.json import JSONValue

__all__ = ("InstallStatusOptions", "InstallStatusReporter")


def _make_operation_id() -> str:
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    return f"soai-install-{stamp}-{os.getpid()}"


@dataclass(frozen=True, slots=True)
class InstallStatusOptions:
    silent: bool
    json_events: bool
    status_file: str


@dataclass(slots=True)
class InstallStatusReporter:
    options: InstallStatusOptions
    operation_id: str = field(default_factory=_make_operation_id)
    completed_stages: list[str] = field(default_factory=list[str])

    def emit_stage(
        self,
        *,
        install_root: str,
        operation: str,
        stage: str,
        state: str,
        message: str,
    ) -> None:
        if state == "completed" and stage not in self.completed_stages:
            self.completed_stages.append(stage)
        timestamp = utc_now_log_format()
        self._write_status(
            install_root=install_root,
            operation=operation,
            stage=stage,
            state=state,
            message=message,
            timestamp=timestamp,
        )
        if self.options.json_events:
            event: dict[str, JSONValue] = {
                "schema_version": 1,
                "event_type": "soai.install.stage",
                "operation_id": self.operation_id,
                "operation": operation,
                "stage": stage,
                "state": state,
                "message": message,
                "timestamp": timestamp,
            }
            sys.stdout.write(serialize_json_compact_stable_strict(event, ensure_ascii=False))
            sys.stdout.write("\n")
            sys.stdout.flush()
        elif not self.options.silent:
            emit("INFO", message)

    def _write_status(
        self,
        *,
        install_root: str,
        operation: str,
        stage: str,
        state: str,
        message: str,
        timestamp: str,
    ) -> None:
        status_path = self.options.status_file
        if not status_path:
            status_path = join_data_abs(install_root, "state", "install-status.json")
        status_dir = os.path.dirname(status_path)
        if status_dir:
            os.makedirs(status_dir, exist_ok=True)
        payload: dict[str, JSONValue] = {
            "schema_version": 1,
            "operation_id": self.operation_id,
            "operation": operation,
            "stage": stage,
            "state": state,
            "message": message,
            "completed_stages": list(self.completed_stages),
            "timestamp": timestamp,
        }
        atomic_write_text_content(
            status_path,
            f"{serialize_json_pretty_sorted_strict(payload, ensure_ascii=False)}\n",
            encoding="utf-8",
            errors="strict",
            ensure_parent=False,
            fsync=True,
        )
