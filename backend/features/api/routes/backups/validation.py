"""SoAI - Backup route ID validation helpers [backend/features/api/routes/backups/validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request

from core.backup.manifest import validate_backup_id
from core.errors.exceptions import SecurityError, ValidationError
from features.api.runtime.errors import raise_invalid_request

__all__ = ("resolve_validated_backup_id",)


def resolve_validated_backup_id(request: Request, backup_id: str) -> str:
    try:
        return validate_backup_id(backup_id)
    except ValidationError as validation_exception:
        raise_invalid_request(request, validation_exception.message)
    except SecurityError as security_exception:
        raise_invalid_request(request, security_exception.message)
