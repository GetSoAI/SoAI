"""SoAI - MCP internal utility tool definition: hardware_benchmark [backend/mcp/tools/utility_tool_definitions/hardware_benchmark.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.hardware.soaibench_limits import (
    SOAIBENCH_HISTORY_DEFAULT_LIMIT,
    SOAIBENCH_LIST_MAX_LIMIT,
    SOAIBENCH_LIST_MIN_LIMIT,
    SOAIBENCH_TEMPERATURE_LIMIT_MAX_CELSIUS,
    SOAIBENCH_TEMPERATURE_LIMIT_MIN_CELSIUS,
)
from core.mcp.schema import build_tool_annotation_flags
from mcp.tools.utility_tool_definitions.hardware_schema import (
    build_hardware_tool_definition,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_hardware_benchmark_tool_definitions",)


def build_hardware_benchmark_tool_definitions() -> dict[str, JSONDict]:
    return {
        "hardware_benchmark": build_hardware_tool_definition(
            title="Hardware Benchmark",
            description=(
                "OpenCL GPU benchmark and stress tool. profile=soaibench runs certified SoAIBench "
                "for comparable validation; profile=stress_test runs the stress workload for "
                "thermal or instability hunting. Requires approval. Poll status until the run is terminal."
            ),
            properties={
                "action": {
                    "type": "string",
                    "enum": ["start", "status", "stop", "history"],
                    "description": (
                        "start launches a run, status polls a run_id, stop requests cancellation, "
                        "history lists previous runs for a device."
                    ),
                },
                "device_id": {
                    "type": ["string", "null"],
                    "minLength": 1,
                    "description": "GPU device_id from hardware_snapshot or hardware_control list.",
                },
                "run_id": {
                    "type": ["string", "null"],
                    "minLength": 1,
                    "description": "SoAIBench run_id returned by start, status, or history.",
                },
                "profile": {
                    "type": ["string", "null"],
                    "enum": ["soaibench", "stress_test", None],
                    "description": (
                        "soaibench runs certified SoAIBench; stress_test runs the stress workload."
                    ),
                },
                "temperature_limit_celsius": {
                    "type": ["number", "null"],
                    "minimum": SOAIBENCH_TEMPERATURE_LIMIT_MIN_CELSIUS,
                    "maximum": SOAIBENCH_TEMPERATURE_LIMIT_MAX_CELSIUS,
                    "description": (
                        "Optional caller-selected temperature checkpoint stop threshold. "
                        "There is no default, and an in-flight benchmark phase is not interrupted."
                    ),
                },
                "history_limit": {
                    "type": ["integer", "null"],
                    "minimum": SOAIBENCH_LIST_MIN_LIMIT,
                    "maximum": SOAIBENCH_LIST_MAX_LIMIT,
                    "default": SOAIBENCH_HISTORY_DEFAULT_LIMIT,
                    "description": "Maximum number of historical runs to return.",
                },
            },
            annotations={
                **build_tool_annotation_flags(destructive=True),
                "requiresApprovalHint": True,
            },
        ),
    }
