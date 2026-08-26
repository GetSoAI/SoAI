"""SoAI - Config manager event handlers [backend/app/config/event_handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from app.config.commented_maps import build_commented_map
from app.config.internal_protocols import ConfigCommandTargetProtocol
from core.concurrency.queue_ops import put_nowait_with_overwrite
from core.config.changes import (
    compute_core_changed_config_areas,
    compute_top_level_changed_keys,
)
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.events.types_system import (
    TriggerConfigReconciliationCommand,
    TriggerConfigScanCommand,
    UpdateConfigCommand,
    UpdateConfigResultEvent,
)
from core.logging.trace import get_context_trace_id
from core.serialization.json import normalize_for_json
from core.types.json_value import coerce_json_dict

__all__ = ("ConfigCommandHandlers",)

OPERATION = "config_manager.update_config_command"


@dataclass(frozen=True, slots=True)
class ConfigCommandHandlers:
    target: ConfigCommandTargetProtocol

    async def handle_reconciliation_trigger(self, command: Event) -> None:
        if not isinstance(command, TriggerConfigReconciliationCommand):
            return
        self.target.logger.info(
            "Received command to reconcile configuration state. Reason: %s",
            command.reason,
        )
        await self.target.establish_baseline()

    async def handle_scan_trigger(self, command: Event) -> None:
        if not isinstance(command, TriggerConfigScanCommand):
            return
        reason = str(command.reason or "").strip()
        source = f"scan:{reason}" if reason else "scan"
        await self.target.trigger_scan(config_name=command.config_name, source=source)

    async def handle_update_config_command(self, command: Event) -> None:
        if not isinstance(command, UpdateConfigCommand):
            return
        reply_channel, context = command.reply_channel, command.context
        trace_id = get_context_trace_id(context)
        try:
            config_name = str(command.config_name).strip()
            if not config_name:
                raise ValidationError("config_name is required")
            if not isinstance(command.new_data, dict):
                raise ValidationError("new_data must be a mapping")
            existing = await self.target.load_config(config_name, force_reload=True)
            before_plain = (
                coerce_json_dict(normalize_for_json(existing)) if existing is not None else {}
            )
            if before_plain is None:
                before_plain = {}
            data = build_commented_map(command.new_data)
            after_plain = coerce_json_dict(normalize_for_json(data))
            if after_plain is None:
                after_plain = {}
            if config_name == "core":
                changed = compute_core_changed_config_areas(
                    previous=before_plain,
                    current=after_plain,
                )
            else:
                changed = compute_top_level_changed_keys(
                    previous=before_plain,
                    current=after_plain,
                )
            await self.target.save_config(
                config_name,
                data,
                source="update_config_command",
                changed_keys=changed,
            )
            delivery = put_nowait_with_overwrite(
                reply_channel,
                UpdateConfigResultEvent(
                    success=True,
                    config_name=config_name,
                    changed_keys=tuple(sorted(changed)),
                ),
                overwrite_attempts=1,
            )
            if not delivery.delivered:
                self.target.logger.warning(
                    "Reply channel full; dropping UpdateConfigResultEvent (success).",
                )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self.target.logger,
                exception,
                message="Failed to process UpdateConfigCommand",
                trace_id=trace_id,
                operation=OPERATION,
                details={"config_name": command.config_name},
            )
            delivery = put_nowait_with_overwrite(
                reply_channel,
                UpdateConfigResultEvent(
                    success=False,
                    config_name=str(command.config_name or ""),
                    error=str(exception),
                ),
                overwrite_attempts=1,
            )
            if not delivery.delivered:
                self.target.logger.warning(
                    "Reply channel full; dropping UpdateConfigResultEvent (failure).",
                )
