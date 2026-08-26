"""SoAI - Runtime execution of canonical power operations [backend/features/api/runtime/power_operation_dispatch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.app.protocols import ApplicationControlProtocol
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError
from core.events.types_system import SoAIMainState
from core.runtime.platform import get_runtime_platform
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.state.protocols import StateAggregatorProtocol
from core.system.power_actions import build_power_terminal_action, resolve_power_action
from core.system.power_operations import PowerOperation, PowerOperationAction
from core.system.privileges import is_admin
from core.terminal.protocols import TerminalServiceProtocol

__all__ = (
    "PowerDispatchFailure",
    "PowerOperationDispatcher",
    "PowerOperationDispatcherDependencies",
)


class PowerDispatchFailure(StateError):
    code: str | int = "power_dispatch_failed"


@dataclass(frozen=True, slots=True)
class PowerOperationDispatcherDependencies:
    application_control: ApplicationControlProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    state_aggregator: StateAggregatorProtocol
    terminal: TerminalServiceProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PowerOperationDispatcherDependencies",
            application_control=self.application_control,
            runtime_flags=self.runtime_flags,
            state_aggregator=self.state_aggregator,
            terminal=self.terminal,
        )


class PowerOperationDispatcher:
    def __init__(self, deps: PowerOperationDispatcherDependencies) -> None:
        self._application_control = deps.application_control
        self._runtime_flags = deps.runtime_flags
        self._state_aggregator = deps.state_aggregator
        self._terminal = deps.terminal

    async def dispatch(self, operation: PowerOperation) -> str:
        if operation.action is PowerOperationAction.APPLICATION_RESTART:
            accepted = self._application_control.restart()
            reason = "application_restart_initiated"
        elif operation.action is PowerOperationAction.APPLICATION_SHUTDOWN:
            accepted = self._application_control.request_shutdown(
                f"power_operation:{operation.operation_id}"
            )
            reason = "application_shutdown_initiated"
        else:
            accepted = await self._dispatch_host_action(operation)
            reason = f"{operation.action.value}_initiated"
        if not accepted:
            raise PowerDispatchFailure(
                "Power operation was rejected because shutdown is already in progress.",
                details={"error_code": "power_already_stopping"},
            )
        if operation.action not in {
            PowerOperationAction.HOST_SUSPEND,
            PowerOperationAction.HOST_HIBERNATE,
        }:
            await self._state_aggregator.set_main_state(SoAIMainState.STOPPING, reason)
        return "power_initiated"

    async def _dispatch_host_action(self, operation: PowerOperation) -> bool:
        if self._runtime_flags.host_system_actions_disabled:
            raise PowerDispatchFailure(
                "Host power actions are disabled by runtime policy.",
                details={"error_code": "power_policy_disabled"},
            )
        host_action = resolve_power_action(operation.action)
        runtime_platform = get_runtime_platform()
        terminal_action, arguments = build_power_terminal_action(
            host_action,
            force=operation.force,
            is_windows=runtime_platform.is_windows,
            is_linux=runtime_platform.is_linux,
            is_macos=runtime_platform.is_macos,
        )
        use_sudo = not runtime_platform.is_windows and not is_admin()
        success, _message = await self._terminal.system_action(
            terminal_action,
            arguments,
            use_sudo=use_sudo,
        )
        if not success:
            raise PowerDispatchFailure(
                "Host power command failed.",
                details={"error_code": "power_command_failed"},
            )
        return True
