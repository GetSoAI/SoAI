"""SoAI - Purger process bootstrap source [backend/app/purger/script.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("PURGER_SCRIPT",)

PURGER_SCRIPT = """\
from app.purger.worker import run_restart_purge_worker
from core.runtime.event_loop_runner import run_coroutine_in_new_event_loop

raise SystemExit(run_coroutine_in_new_event_loop(run_restart_purge_worker()))
"""
