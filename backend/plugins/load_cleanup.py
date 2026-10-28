"""SoAI - Plugin load primary failure preservation [backend/plugins/load_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("preserve_plugin_load_failure",)


def preserve_plugin_load_failure(
    primary_exception: BaseException | None,
    cleanup_exception: BaseException | None,
) -> None:
    if (
        primary_exception is None
        or cleanup_exception is None
        or cleanup_exception is primary_exception
    ):
        return
    primary_exception.add_note(f"Acquired plugin worker cleanup also failed: {cleanup_exception}")
    raise primary_exception from primary_exception.__cause__
