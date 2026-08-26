"""SoAI - Workspace startup security hardening warnings [backend/core/security/workspace_hardening_warnings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass

from core.files.path_policy import is_path_within_base, is_same_path
from core.security.hardening_types import SecurityHardeningIssue
from core.workspaces.conversation_workspace_path import (
    fingerprint_conversation_workspace_root,
)

__all__ = (
    "UserWorkspaceHardeningSnapshot",
    "WORKSPACE_USER_PROFILE_REFERENCE",
    "collect_user_workspace_hardening_issues",
    "user_workspace_hardening_check_failed_issue",
    "user_workspace_invalid_hardening_issue",
)

WORKSPACE_USER_PROFILE_REFERENCE = "webui_users.workspace_path"


@dataclass(frozen=True, slots=True)
class UserWorkspaceHardeningSnapshot:
    user_id: int
    username: str
    resolved_workspace_path: str


def _user_reference(*, user_id: int | None, username: str | None) -> str:
    if user_id is None and username is None:
        return "user_id=unavailable username=unavailable"
    if user_id is None:
        return f"user_id=unavailable username={username}"
    if username is None:
        return f"user_id={user_id} username=unavailable"
    return f"user_id={user_id} username={username}"


def _workspace_fingerprint(path: str) -> str:
    resolved = os.path.realpath(os.path.abspath(path))
    return fingerprint_conversation_workspace_root(resolved)


def _workspace_issue(
    *,
    issue_id: str,
    snapshot: UserWorkspaceHardeningSnapshot,
    relation: str,
) -> SecurityHardeningIssue:
    return SecurityHardeningIssue(
        issue_id=issue_id,
        message=(
            "A WebUI user workspace resolves "
            f"{relation}. {_user_reference(user_id=snapshot.user_id, username=snapshot.username)} "
            f"workspace_fingerprint={_workspace_fingerprint(snapshot.resolved_workspace_path)}. "
            "Prompt-injected workspace file operations could modify SoAI code, plugins, "
            "configuration, logs, or the database. Move this user's workspace to a path that "
            "does not contain or reside inside the SoAI install directory."
        ),
        config_keys=(),
        workspace_references=(WORKSPACE_USER_PROFILE_REFERENCE,),
    )


def user_workspace_invalid_hardening_issue(
    *,
    user_id: int | None,
    username: str | None,
) -> SecurityHardeningIssue:
    return SecurityHardeningIssue(
        issue_id="webui_workspace_path_invalid",
        message=(
            "A WebUI user workspace path could not be resolved during startup hardening "
            f"checks. {_user_reference(user_id=user_id, username=username)}. Review and repair "
            "the configured workspace before exposing SoAI."
        ),
        config_keys=(),
        workspace_references=(WORKSPACE_USER_PROFILE_REFERENCE,),
    )


def user_workspace_hardening_check_failed_issue() -> SecurityHardeningIssue:
    return SecurityHardeningIssue(
        issue_id="webui_workspace_hardening_check_failed",
        message=(
            "WebUI user workspace hardening checks could not read the user workspace "
            "snapshot. Review startup logs before exposing SoAI."
        ),
        config_keys=(),
        workspace_references=(WORKSPACE_USER_PROFILE_REFERENCE,),
    )


def collect_user_workspace_hardening_issues(
    *,
    soai_root_path: str,
    workspaces: tuple[UserWorkspaceHardeningSnapshot, ...],
) -> tuple[SecurityHardeningIssue, ...]:
    soai_root_real = os.path.realpath(os.path.abspath(soai_root_path))
    issues: list[SecurityHardeningIssue] = []
    for snapshot in workspaces:
        workspace_real = os.path.realpath(os.path.abspath(snapshot.resolved_workspace_path))
        normalized_snapshot = UserWorkspaceHardeningSnapshot(
            user_id=snapshot.user_id,
            username=snapshot.username,
            resolved_workspace_path=workspace_real,
        )
        if is_same_path(soai_root_real, workspace_real):
            issues.append(
                _workspace_issue(
                    issue_id="webui_workspace_is_soai_root",
                    snapshot=normalized_snapshot,
                    relation="to the SoAI install root",
                ),
            )
        elif is_path_within_base(soai_root_real, workspace_real):
            issues.append(
                _workspace_issue(
                    issue_id="webui_workspace_inside_soai_root",
                    snapshot=normalized_snapshot,
                    relation="inside the SoAI install root",
                ),
            )
        elif is_path_within_base(workspace_real, soai_root_real):
            issues.append(
                _workspace_issue(
                    issue_id="webui_workspace_contains_soai_root",
                    snapshot=normalized_snapshot,
                    relation="to an ancestor of the SoAI install root",
                ),
            )
    return tuple(issues)
