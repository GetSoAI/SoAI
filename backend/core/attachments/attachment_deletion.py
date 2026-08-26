"""SoAI - Conversation attachment deletion plan [backend/core/attachments/attachment_deletion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("AttachmentDeletionPlan",)


@dataclass(frozen=True, slots=True)
class AttachmentDeletionPlan:
    requires_file_deletion: bool
