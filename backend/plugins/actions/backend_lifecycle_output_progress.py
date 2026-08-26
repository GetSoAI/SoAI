"""SoAI - Plugin backend lifecycle output progress reporting [backend/plugins/actions/backend_lifecycle_output_progress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ast
import asyncio
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import cancel_and_await
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.progress.percent import clamp_percent, coerce_optional_percent
from core.serialization.json_parsing import parse_json_value
from core.types.json import JSONValue, is_json_value
from plugins.actions.progress import send_progress_with_task

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.logging.protocols import LoggerProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from core.tasks.protocols_operations import SendTaskProgressEventCallable
    from core.types.json import JSONDict

__all__ = ("LifecycleOutputProgressReporter",)

OPERATION_PLUGIN_FLOW_EXECUTE_LIFECYCLE_TASK_OUTPUT_CALLBACK_FLUSH = (
    "plugin_flow.execute_lifecycle_task.output_callback.flush"
)
OPERATION_PLUGIN_FLOW_EXECUTE_LIFECYCLE_TASK_OUTPUT_CALLBACK_SEND_PROGRESS = (
    "plugin_flow.execute_lifecycle_task.output_callback.send_progress"
)
MAX_STRUCTURED_OUTPUT_PAYLOAD_BYTES = 8192


def _coerce_progress_text(value: JSONValue) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, int | float) and not isinstance(value, bool):
        return str(value).strip()
    return ""


def _literal_node_to_json_value(node: ast.AST) -> tuple[bool, JSONValue]:
    if isinstance(node, ast.Constant):
        value = node.value
        if value is None or isinstance(value, str | int | float | bool):
            return (True, value)
        return (False, None)
    if isinstance(node, ast.List | ast.Tuple):
        items: list[JSONValue] = []
        for element in node.elts:
            valid, item = _literal_node_to_json_value(element)
            if not valid:
                return (False, None)
            items.append(item)
        return (True, items)
    if isinstance(node, ast.Dict):
        result: JSONDict = {}
        for key_node, value_node in zip(node.keys, node.values, strict=True):
            if key_node is None:
                return (False, None)
            valid_key, key_value = _literal_node_to_json_value(key_node)
            valid_value, item_value = _literal_node_to_json_value(value_node)
            if not valid_key or not isinstance(key_value, str) or not valid_value:
                return (False, None)
            result[key_value] = item_value
        return (True, result)
    return (False, None)


def _parse_literal_json_mapping(value: str) -> JSONValue | None:
    try:
        expression = ast.parse(value, mode="eval")
    except SyntaxError:
        return None
    valid, parsed = _literal_node_to_json_value(expression.body)
    return parsed if valid and isinstance(parsed, Mapping) else None


def _normalize_output_payload_from_string(
    payload: str,
) -> tuple[str, int | None, JSONValue | None]:
    stripped = payload.strip()
    if not stripped:
        return "", None, None
    if not (
        (stripped.startswith("{") and stripped.endswith("}"))
        or (stripped.startswith("[") and stripped.endswith("]"))
    ):
        return stripped, None, None
    parsed_json: JSONValue | None = None
    try:
        parsed_json = parse_json_value(stripped, field="progress payload")
    except ValidationError:
        parsed_json = None
    if isinstance(parsed_json, Mapping):
        return _normalize_output_payload(parsed_json)
    if len(stripped.encode("utf-8")) <= MAX_STRUCTURED_OUTPUT_PAYLOAD_BYTES:
        parsed_literal = _parse_literal_json_mapping(stripped)
        if parsed_literal is not None:
            return _normalize_output_payload(parsed_literal)
    return stripped, None, None


def _normalize_output_payload(
    payload: JSONValue,
) -> tuple[str, int | None, JSONValue | None]:
    if isinstance(payload, str):
        return _normalize_output_payload_from_string(payload)
    if isinstance(payload, Mapping):
        message = _coerce_progress_text(payload.get("message"))
        if not message:
            message = _coerce_progress_text(payload.get("status_message"))
        details = payload.get("details")
        percent = coerce_optional_percent(payload.get("percent"))
        progress_percent = coerce_optional_percent(payload.get("progress"))
        normalized_percent = percent if percent is not None else progress_percent
        normalized_details: JSONValue | None = None
        if isinstance(details, str):
            stripped_details = details.strip()
            normalized_details = stripped_details or None
        elif is_json_value(details):
            normalized_details = details
        return message, normalized_percent, normalized_details
    return _coerce_progress_text(payload), None, None


class LifecycleOutputProgressReporter:
    __slots__ = (
        "_action",
        "_display_name",
        "_last_percent_sent",
        "_logger",
        "_output_send_tasks",
        "_progress_mapper",
        "_reply_channel",
        "_send_task_progress_event",
        "_task_id",
        "_task_registry",
        "_trace_id",
    )

    def __init__(
        self,
        *,
        logger: LoggerProtocol,
        trace_id: str,
        action: str,
        display_name: str,
        reply_channel: asyncio.Queue[Event] | None,
        task_id: str | None,
        task_registry: TaskRegistryProtocol,
        send_task_progress_event: SendTaskProgressEventCallable | None,
        progress_mapper: Callable[[int], int] | None,
    ) -> None:
        self._logger = logger
        self._trace_id = trace_id
        self._action = action
        self._display_name = display_name
        self._reply_channel = reply_channel
        self._task_id = task_id
        self._task_registry = task_registry
        self._send_task_progress_event = send_task_progress_event
        self._progress_mapper = progress_mapper
        self._last_percent_sent = -1
        self._output_send_tasks: set[asyncio.Task[None]] = set()

    def map_progress(self, percent: int) -> int:
        clamped = clamp_percent(percent)
        mapped = (
            clamp_percent(self._progress_mapper(clamped))
            if self._progress_mapper is not None
            else clamped
        )
        self._last_percent_sent = max(mapped, self._last_percent_sent)
        return self._last_percent_sent

    def _bump_output_progress(self) -> int:
        self._last_percent_sent = min(self._last_percent_sent + 1, 95)
        return self._last_percent_sent

    def _record_output_send_task(self, task: asyncio.Task[None]) -> None:
        self._output_send_tasks.add(task)

        def on_done(done_task: asyncio.Task[None]) -> None:
            self._output_send_tasks.discard(done_task)
            try:
                done_task.result()
            except asyncio.CancelledError:
                return
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    self._logger,
                    exception,
                    message="Failed to send plugin lifecycle output progress update (non-critical).",
                    operation=OPERATION_PLUGIN_FLOW_EXECUTE_LIFECYCLE_TASK_OUTPUT_CALLBACK_SEND_PROGRESS,
                    details={
                        "trace_id": self._trace_id,
                        "action": self._action,
                        "plugin": self._display_name,
                    },
                    level="debug",
                )

        task.add_done_callback(on_done)

    def output_callback(self, line: JSONValue) -> asyncio.Task[None] | None:
        normalized_message, normalized_percent, normalized_details = _normalize_output_payload(line)
        if not normalized_message:
            return None

        async def _send() -> None:
            try:
                await send_progress_with_task(
                    self._reply_channel,
                    self._task_id,
                    self.map_progress(
                        (
                            normalized_percent
                            if normalized_percent is not None
                            else self._bump_output_progress()
                        ),
                    ),
                    f"[{self._display_name}] {normalized_message}",
                    self._task_registry,
                    self._send_task_progress_event,
                    details=normalized_details,
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    self._logger,
                    exception,
                    message="Failed to send plugin lifecycle output progress update (non-critical).",
                    operation=OPERATION_PLUGIN_FLOW_EXECUTE_LIFECYCLE_TASK_OUTPUT_CALLBACK_SEND_PROGRESS,
                    details={
                        "trace_id": self._trace_id,
                        "action": self._action,
                        "plugin": self._display_name,
                    },
                    level="debug",
                )

        task = create_ephemeral_task(_send())
        self._record_output_send_task(task)
        return task

    async def flush(self) -> None:
        if not self._output_send_tasks:
            return
        pending_tasks = list(self._output_send_tasks)
        for pending_task in pending_tasks:
            try:
                await pending_task
            except asyncio.CancelledError:
                for task in pending_tasks:
                    task.cancel()
                await uncancel_then_cleanup(cancel_and_await(pending_tasks))
                for task in pending_tasks:
                    if task.cancelled():
                        continue
                    exception = task.exception()
                    if exception is None:
                        continue
                    log_handled_exception(
                        self._logger,
                        exception,
                        message="Plugin lifecycle output flush cleanup raised (non-critical).",
                        operation=OPERATION_PLUGIN_FLOW_EXECUTE_LIFECYCLE_TASK_OUTPUT_CALLBACK_FLUSH,
                        details={
                            "trace_id": self._trace_id,
                            "action": self._action,
                            "plugin": self._display_name,
                        },
                        level="debug",
                    )
                raise
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    self._logger,
                    exception,
                    message="Failed to flush plugin lifecycle output progress update (non-critical).",
                    operation=OPERATION_PLUGIN_FLOW_EXECUTE_LIFECYCLE_TASK_OUTPUT_CALLBACK_FLUSH,
                    details={
                        "trace_id": self._trace_id,
                        "action": self._action,
                        "plugin": self._display_name,
                    },
                    level="debug",
                )
