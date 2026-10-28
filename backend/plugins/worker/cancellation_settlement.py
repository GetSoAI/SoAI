"""SoAI - Plugin worker calls settled after parent cancellation [backend/plugins/worker/cancellation_settlement.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("CANCELLATION_SETTLED_WORKER_METHODS", "BACKEND_LIFECYCLE_WORKER_METHODS")

BACKEND_LIFECYCLE_WORKER_METHODS: frozenset[str] = frozenset(
    {"call.install_backend", "call.update_backend", "call.cleanup_partial_installation"}
)
CANCELLATION_SETTLED_WORKER_METHODS: frozenset[str] = frozenset(
    ("call.discover_models", "call.handle_request", *BACKEND_LIFECYCLE_WORKER_METHODS)
)
