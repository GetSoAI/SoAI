"""SoAI - WebUI workspace security hardening collection [backend/core/security/workspace_hardening_collection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.workspace_path import resolve_workspace_real_path
from core.logging.trace import get_logger
from core.security.hardening_types import SecurityHardeningIssue
from core.security.workspace_hardening_warnings import (
    UserWorkspaceHardeningSnapshot,
    collect_user_workspace_hardening_issues,
    user_workspace_hardening_check_failed_issue,
    user_workspace_invalid_hardening_issue,
)
from core.validation.strict_numbers import require_positive_int_strict
from core.workspaces.user_workspace_path import (
    require_user_record_username,
    require_user_record_workspace_path,
)

if TYPE_CHECKING:
    from core.files.protocols import FilesPathResolverProtocol
    from core.types.json import JSONDict
    from core.users.protocols_database import DatabaseUsersProtocol

__all__ = (
    "WorkspaceHardeningCollectionDependencies",
    "collect_workspace_hardening_issues",
)

LOGGER_NAME = "SoAI.core.security.workspace_hardening_collection"
OPERATION_COLLECT_WORKSPACE_HARDENING = "workspace_hardening.collect"


@dataclass(frozen=True, slots=True)
class WorkspaceHardeningCollectionDependencies:
    base_dir: str
    files: FilesPathResolverProtocol
    database_users: DatabaseUsersProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="WorkspaceHardeningCollectionDependencies",
            base_dir=self.base_dir,
            database_users=self.database_users,
            files=self.files,
        )
        if not isinstance(self.base_dir, str) or not self.base_dir.strip():
            raise ValidationError("Application base_dir is required.")


def _read_user_identifier(user: JSONDict) -> tuple[int | None, str | None]:
    user_id: int | None = None
    username: str | None = None
    try:
        user_id = require_positive_int_strict(
            user.get("id"),
            error_message="User id must be a positive integer.",
        )
    except ValidationError:
        user_id = None
    try:
        username = require_user_record_username(user)
    except StateError:
        username = None
    return user_id, username


def _build_user_workspace_snapshot(
    deps: WorkspaceHardeningCollectionDependencies,
    user: JSONDict,
) -> UserWorkspaceHardeningSnapshot | SecurityHardeningIssue:
    user_id, username = _read_user_identifier(user)
    try:
        valid_user_id = require_positive_int_strict(
            user.get("id"),
            error_message="User id must be a positive integer.",
        )
        valid_username = require_user_record_username(user)
        workspace_path = require_user_record_workspace_path(user)
        resolved_workspace_path = resolve_workspace_real_path(
            deps.files,
            workspace_path,
        )
    except (StateError, ValidationError):
        return user_workspace_invalid_hardening_issue(
            user_id=user_id,
            username=username,
        )
    return UserWorkspaceHardeningSnapshot(
        user_id=valid_user_id,
        username=valid_username,
        resolved_workspace_path=resolved_workspace_path,
    )


async def collect_workspace_hardening_issues(
    deps: WorkspaceHardeningCollectionDependencies,
) -> tuple[SecurityHardeningIssue, ...]:
    try:
        users = await deps.database_users.list_all_accounts()
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to collect WebUI workspace hardening snapshot.",
            operation=OPERATION_COLLECT_WORKSPACE_HARDENING,
            level="warning",
        )
        return (user_workspace_hardening_check_failed_issue(),)
    snapshots: list[UserWorkspaceHardeningSnapshot] = []
    issues: list[SecurityHardeningIssue] = []
    for user in users:
        snapshot = _build_user_workspace_snapshot(deps, user)
        if isinstance(snapshot, SecurityHardeningIssue):
            issues.append(snapshot)
        else:
            snapshots.append(snapshot)
    issues.extend(
        collect_user_workspace_hardening_issues(
            soai_root_path=os.path.realpath(os.path.abspath(deps.base_dir)),
            workspaces=tuple(snapshots),
        ),
    )
    return tuple(issues)
