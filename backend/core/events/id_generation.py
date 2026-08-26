"""SoAI - Event ID generation [backend/core/events/id_generation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import uuid

__all__ = ("generate_event_id",)


def generate_event_id() -> str:
    return f"evt_{uuid.uuid4().hex}"
