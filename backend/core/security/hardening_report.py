"""SoAI - Security hardening report serialization [backend/core/security/hardening_report.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.security.hardening_types import SecurityHardeningIssue
from core.types.json import JSONDict, JSONValue

__all__ = ("build_security_hardening_report",)


def _append_unique(target: list[str], values: tuple[str, ...]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def _issue_to_json(issue: SecurityHardeningIssue) -> JSONDict:
    return {
        "issue_id": issue.issue_id,
        "message": issue.message,
        "config_keys": list(issue.config_keys),
        "workspace_references": list(issue.workspace_references),
    }


def build_security_hardening_report(
    issues: tuple[SecurityHardeningIssue, ...],
) -> JSONDict:
    config_keys: list[str] = []
    workspace_references: list[str] = []
    findings: list[JSONValue] = []
    for issue in issues:
        _append_unique(config_keys, issue.config_keys)
        _append_unique(workspace_references, issue.workspace_references)
        findings.append(_issue_to_json(issue))
    return {
        "secure": not findings,
        "issue_count": len(findings),
        "findings": findings,
        "config_keys": config_keys,
        "workspace_references": workspace_references,
    }
