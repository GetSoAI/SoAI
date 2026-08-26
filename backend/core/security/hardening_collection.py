"""SoAI - Complete security hardening issue collection [backend/core/security/hardening_collection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.auth.openai_protection import OpenAIProtectionState
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.security.admin_session_hardening import collect_admin_session_hardening_issues
from core.security.hardening_types import SecurityHardeningIssue
from core.security.hardening_warnings import (
    collect_security_hardening_issues,
    is_network_exposure_configured,
)
from core.security.workspace_hardening_collection import (
    WorkspaceHardeningCollectionDependencies,
    collect_workspace_hardening_issues,
)
from core.users.bootstrap_state import BootstrapState
from core.validation.strict_numbers import require_non_negative_int_strict

if TYPE_CHECKING:
    from core.auth.protocols_database_api_keys import DatabaseAPIKeysProtocol
    from core.auth.protocols_database_mcp_access_tokens import (
        DatabaseMcpAccessTokensProtocol,
    )
    from core.auth.protocols_database_tokens import DatabaseTokensProtocol
    from core.config.protocols import ConfigProtocol
    from core.files.protocols import FilesPathResolverProtocol
    from core.users.protocols_database import DatabaseUsersProtocol

__all__ = (
    "SecurityHardeningCollectionDependencies",
    "collect_complete_security_hardening_issues",
)

LOGGER_NAME = "SoAI.core.security.hardening_collection"
OPERATION_COLLECT_CREDENTIAL_HARDENING = "security_hardening.collect_credentials"


@dataclass(frozen=True, slots=True)
class SecurityHardeningCollectionDependencies:
    base_dir: str
    files: FilesPathResolverProtocol
    database_users: DatabaseUsersProtocol
    database_tokens: DatabaseTokensProtocol
    database_api_keys: DatabaseAPIKeysProtocol
    database_mcp_access_tokens: DatabaseMcpAccessTokensProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="SecurityHardeningCollectionDependencies",
            base_dir=self.base_dir,
            database_api_keys=self.database_api_keys,
            database_mcp_access_tokens=self.database_mcp_access_tokens,
            database_tokens=self.database_tokens,
            database_users=self.database_users,
            files=self.files,
        )
        if not isinstance(self.base_dir, str) or not self.base_dir.strip():
            raise ValidationError("Application base_dir is required.")


def _credential_hardening_check_failed_issue() -> SecurityHardeningIssue:
    return SecurityHardeningIssue(
        issue_id="credential_hardening_check_failed",
        message=(
            "Credential hardening checks could not read the authoritative credential registry. "
            "Review backend logs before exposing SoAI."
        ),
        config_keys=(),
    )


async def _collect_credential_hardening_issues(
    config: ConfigProtocol,
    deps: SecurityHardeningCollectionDependencies,
) -> tuple[SecurityHardeningIssue, ...]:
    try:
        bootstrap_state = await deps.database_users.get_bootstrap_state()
        api_keys_without_expiration = require_non_negative_int_strict(
            await deps.database_api_keys.count_non_revoked_keys_without_expiration(),
            error_message="API keys without expiration count must be non-negative.",
        )
        mcp_tokens_without_expiration = 0
        if config.get_bool("TOOLS.MCP.ENABLED") and config.get_bool(
            "TOOLS.MCP.SERVER_MODE.ENABLED"
        ):
            mcp_tokens_without_expiration = require_non_negative_int_strict(
                await deps.database_mcp_access_tokens.count_non_revoked_tokens_without_expiration(),
                error_message="MCP access tokens without expiration count must be non-negative.",
            )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to collect credential hardening snapshot.",
            operation=OPERATION_COLLECT_CREDENTIAL_HARDENING,
            level="warning",
        )
        return (_credential_hardening_check_failed_issue(),)
    issues: list[SecurityHardeningIssue] = []
    protection_state = deps.database_api_keys.protection_state
    if bootstrap_state is BootstrapState.COMPLETE and is_network_exposure_configured(config):
        if protection_state is OpenAIProtectionState.OPEN:
            issues.append(
                SecurityHardeningIssue(
                    issue_id="openai_api_authentication_not_configured",
                    message=(
                        "Initial setup is complete but the network-exposed OpenAI-compatible and "
                        "Anthropic-compatible APIs do not require an API key. Create an API key "
                        "before exposing SoAI."
                    ),
                    config_keys=(
                        "SERVER.PUBLIC_ORIGIN",
                        "SERVER.HTTP.NETWORK.HOST",
                        "SERVER.HTTP.PROXY.ENABLE_HEADERS",
                        "SERVER.HTTP.PROXY.TRUSTED_NETWORKS",
                    ),
                )
            )
        elif protection_state is OpenAIProtectionState.INDETERMINATE:
            issues.append(
                SecurityHardeningIssue(
                    issue_id="openai_api_authentication_state_indeterminate",
                    message=(
                        "The API-key protection state is indeterminate. Authentication remains "
                        "fail-closed; review backend logs and the API-key registry."
                    ),
                    config_keys=(
                        "SERVER.PUBLIC_ORIGIN",
                        "SERVER.HTTP.NETWORK.HOST",
                        "SERVER.HTTP.PROXY.ENABLE_HEADERS",
                        "SERVER.HTTP.PROXY.TRUSTED_NETWORKS",
                    ),
                )
            )
    if api_keys_without_expiration:
        issues.append(
            SecurityHardeningIssue(
                issue_id="openai_api_keys_without_expiration",
                message=(
                    f"{api_keys_without_expiration} non-revoked OpenAI API key(s) have no "
                    "expiration. Rotate them with finite expiration dates."
                ),
                config_keys=("API.OPENAI.SECURITY.KEY_EXPIRATION.DEFAULT_TTL_DAYS",),
            )
        )
    if mcp_tokens_without_expiration:
        issues.append(
            SecurityHardeningIssue(
                issue_id="mcp_access_tokens_without_expiration",
                message=(
                    f"{mcp_tokens_without_expiration} non-revoked MCP access token(s) have no "
                    "expiration. Rotate them with finite expiration dates."
                ),
                config_keys=(
                    "TOOLS.MCP.ENABLED",
                    "TOOLS.MCP.SERVER_MODE.ENABLED",
                ),
            )
        )
    return tuple(issues)


async def collect_complete_security_hardening_issues(
    config: ConfigProtocol,
    deps: SecurityHardeningCollectionDependencies,
) -> tuple[SecurityHardeningIssue, ...]:
    workspace_deps = WorkspaceHardeningCollectionDependencies(
        base_dir=deps.base_dir,
        files=deps.files,
        database_users=deps.database_users,
    )
    return (
        *collect_security_hardening_issues(config),
        *await collect_workspace_hardening_issues(workspace_deps),
        *await collect_admin_session_hardening_issues(deps.database_tokens),
        *await _collect_credential_hardening_issues(config, deps),
    )
