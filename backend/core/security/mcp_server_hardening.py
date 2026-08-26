"""SoAI - MCP server-mode security hardening findings [backend/core/security/mcp_server_hardening.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.config.protocols import ConfigProtocol, ConfigValue
from core.mcp.server_tool_risk import (
    MCP_SERVER_AUTONOMOUS_EXECUTION_TOOLS,
    MCP_SERVER_BROWSER_TOOLS,
    MCP_SERVER_CONNECTED_ACCOUNT_TOOLS,
    MCP_SERVER_CREDENTIAL_TOOLS,
    MCP_SERVER_FILESYSTEM_TOOLS,
    MCP_SERVER_HOST_COMMAND_TOOLS,
    MCP_SERVER_OPEN_HTTP_TOOLS,
    MCP_SERVER_PERSISTENT_MUTATION_TOOLS,
    MCP_SERVER_PRIVATE_CONTEXT_TOOLS,
    MCP_SERVER_RESOURCE_INTENSIVE_TOOLS,
    MCP_SERVER_SENSITIVE_RESOURCES,
)
from core.security.hardening_types import SecurityHardeningIssue

__all__ = ("collect_mcp_server_hardening_issues",)

_EXPOSED_TOOLS_KEY = "TOOLS.MCP.SERVER_MODE.EXPOSED_TOOLS"
_EXPOSED_RESOURCES_KEY = "TOOLS.MCP.SERVER_MODE.EXPOSED_RESOURCES"


def _normalized_names(value: ConfigValue | None) -> frozenset[str]:
    if isinstance(value, str):
        normalized = value.strip()
        return frozenset({normalized}) if normalized else frozenset()
    if isinstance(value, list | tuple | set | frozenset):
        names: set[str] = set()
        for candidate in value:
            if isinstance(candidate, str) and candidate.strip():
                names.add(candidate.strip())
        return frozenset(names)
    return frozenset()


def _exposed_matches(exposed: frozenset[str], risky: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(exposed.intersection(risky)))


def _tool_finding(
    *,
    issue_id: str,
    message: str,
    exposed_tools: frozenset[str],
    risky_tools: tuple[str, ...],
) -> SecurityHardeningIssue | None:
    matches = _exposed_matches(exposed_tools, risky_tools)
    if not matches:
        return None
    return SecurityHardeningIssue(
        issue_id=issue_id,
        message=(
            f"{message} Exposed tools: {', '.join(matches)}. Use this exposure only for a "
            "trusted local client on a deployment where the security audit has no unresolved "
            "issue that makes the setup unsafe; do not expose these tools to remote clients."
        ),
        config_keys=("TOOLS.MCP.SERVER_MODE.EXPOSED_TOOLS",),
    )


def collect_mcp_server_hardening_issues(
    config: ConfigProtocol,
) -> tuple[SecurityHardeningIssue, ...]:
    if not config.get_bool("TOOLS.MCP.ENABLED") or not config.get_bool(
        "TOOLS.MCP.SERVER_MODE.ENABLED"
    ):
        return ()
    exposed_tools = _normalized_names(config.get(_EXPOSED_TOOLS_KEY))
    candidates = (
        _tool_finding(
            issue_id="mcp_server_host_command_tools_exposed",
            message=(
                "MCP server mode exposes host shell capabilities. Calls execute inside the SoAI "
                "server process without the WebUI approval dialog and inherit its operating-system privileges."
            ),
            exposed_tools=exposed_tools,
            risky_tools=MCP_SERVER_HOST_COMMAND_TOOLS,
        ),
        _tool_finding(
            issue_id="mcp_server_filesystem_tools_exposed",
            message=(
                "MCP server mode exposes server-side workspace file access. A compromised token "
                "can read or mutate files reachable through the token owner's configured workspace."
            ),
            exposed_tools=exposed_tools,
            risky_tools=MCP_SERVER_FILESYSTEM_TOOLS,
        ),
        _tool_finding(
            issue_id="mcp_server_browser_tools_exposed",
            message=(
                "MCP server mode exposes a browser running on the SoAI host. Private-network "
                "requests are blocked, but callers can use persisted web sessions, upload workspace files, and act on public sites."
            ),
            exposed_tools=exposed_tools,
            risky_tools=MCP_SERVER_BROWSER_TOOLS,
        ),
        _tool_finding(
            issue_id="mcp_server_connected_account_tools_exposed",
            message=(
                "MCP server mode exposes linked mail or calendar data and actions. A compromised "
                "token can read private account data or perform remote mutations as its owner."
            ),
            exposed_tools=exposed_tools,
            risky_tools=MCP_SERVER_CONNECTED_ACCOUNT_TOOLS,
        ),
        _tool_finding(
            issue_id="mcp_server_credential_tools_exposed",
            message=(
                "MCP server mode exposes credential-vault capabilities. Callers may enumerate, "
                "delete, request, or use credentials through authenticated browser flows."
            ),
            exposed_tools=exposed_tools,
            risky_tools=MCP_SERVER_CREDENTIAL_TOOLS,
        ),
        _tool_finding(
            issue_id="mcp_server_autonomous_execution_tools_exposed",
            message=(
                "MCP server mode exposes automation or subagent execution. These tools can create "
                "durable or delegated work that continues beyond one direct tool call."
            ),
            exposed_tools=exposed_tools,
            risky_tools=MCP_SERVER_AUTONOMOUS_EXECUTION_TOOLS,
        ),
        _tool_finding(
            issue_id="mcp_server_persistent_mutation_tools_exposed",
            message=(
                "MCP server mode exposes persistent state mutations. A compromised token can alter "
                "knowledge, memory, plans, tasks, or notifications owned by the account."
            ),
            exposed_tools=exposed_tools,
            risky_tools=MCP_SERVER_PERSISTENT_MUTATION_TOOLS,
        ),
        _tool_finding(
            issue_id="mcp_server_private_context_tools_exposed",
            message=(
                "MCP server mode exposes private server-side context or interactive prompts. A "
                "compromised token can read knowledge, memory, plans, or connected MCP resources, "
                "or present requests to the token owner's active WebUI session."
            ),
            exposed_tools=exposed_tools,
            risky_tools=MCP_SERVER_PRIVATE_CONTEXT_TOOLS,
        ),
        _tool_finding(
            issue_id="mcp_server_resource_intensive_tools_exposed",
            message=(
                "MCP server mode exposes resource-intensive processing. A compromised token can "
                "consume inference, media-processing, storage, CPU, or GPU capacity."
            ),
            exposed_tools=exposed_tools,
            risky_tools=MCP_SERVER_RESOURCE_INTENSIVE_TOOLS,
        ),
        _tool_finding(
            issue_id="mcp_server_open_http_tool_exposed",
            message=(
                "MCP server mode exposes arbitrary outbound public HTTP methods. Private-network "
                "egress is separately blocked, but callers can perform state-changing requests to public services."
            ),
            exposed_tools=exposed_tools,
            risky_tools=MCP_SERVER_OPEN_HTTP_TOOLS,
        ),
    )
    issues = [candidate for candidate in candidates if candidate is not None]
    exposed_resources = _normalized_names(config.get(_EXPOSED_RESOURCES_KEY))
    sensitive_resources = _exposed_matches(exposed_resources, MCP_SERVER_SENSITIVE_RESOURCES)
    if sensitive_resources:
        issues.append(
            SecurityHardeningIssue(
                issue_id="mcp_server_sensitive_resources_exposed",
                message=(
                    "MCP server mode exposes private linked-account resources. Exposed resources: "
                    f"{', '.join(sensitive_resources)}. Use this exposure only for a trusted local "
                    "client on a deployment where the security audit has no unresolved issue that "
                    "makes the setup unsafe; do not expose these resources to remote clients."
                ),
                config_keys=("TOOLS.MCP.SERVER_MODE.EXPOSED_RESOURCES",),
            )
        )
    return tuple(issues)
