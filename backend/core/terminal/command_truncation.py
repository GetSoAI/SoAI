"""SoAI - Terminal command truncation helpers [backend/core/terminal/command_truncation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("truncate_shell_command",)


def truncate_shell_command(shell: str, max_chars: int = 200) -> str:
    if max_chars <= 0:
        return ""
    if len(shell) <= max_chars:
        return shell
    ellipsis = "..."
    if max_chars <= len(ellipsis):
        return ellipsis[:max_chars]
    prefix_len = max_chars - len(ellipsis)
    prefix = shell[:prefix_len].rstrip()
    if not prefix:
        return ellipsis[:max_chars]
    return f"{prefix}{ellipsis}"
