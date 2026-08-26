"""SoAI - Durable mutation storage composition contracts [backend/core/mutations/storage_composition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.mutations.protocols import (
    MutationAdmissionHookProtocol,
    MutationRecoveryReleaseProtocol,
)

__all__ = ("MutationStorageComposition",)


@dataclass(frozen=True, slots=True)
class MutationStorageComposition:
    admission_hook: MutationAdmissionHookProtocol | None
    recovery_release: MutationRecoveryReleaseProtocol | None
