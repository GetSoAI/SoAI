"""SoAI - Stable public skill failure codes and safe messages [backend/core/skills/errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import (
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
    SoAIError,
    ValidationError,
)
from core.errors.payload import ErrorPublicPayload
from core.errors.public_projection import apply_public_error_payload, project_specific_public_error
from core.types.json import JSONDict
from core.validation.record_fields import require_int

__all__ = ("build_skill_error", "project_skill_package_error")

if TYPE_CHECKING:
    type SkillErrorReason = Literal[
        "wrapper_name_mismatch",
        "restriction_unsupported",
        "tool_restricted",
        "argument_conflict",
        "alias_ambiguous",
        "manifest_format",
        "invalid_field",
        "source_conflict",
        "archive_integrity",
        "archive_unsafe",
        "archive_unsupported",
        "invalid_filename",
        "resource_limit",
    ]
    type SkillErrorCode = Literal[
        "skill_invalid_package",
        "skill_upload_conflict",
        "skill_name_conflict",
        "skill_library_full",
        "skill_invocation_unavailable",
        "skill_selection_conflict",
        "skill_import_busy",
        "skill_not_found",
        "skill_context_full",
    ]


def build_skill_error(
    code: SkillErrorCode,
    *,
    reason: SkillErrorReason | None = None,
    field: str | None = None,
    locations: tuple[str, str] | None = None,
    measured: int | None = None,
    limit: int | None = None,
    source_position: tuple[int, int] | None = None,
) -> SoAIError:
    failures: dict[SkillErrorCode, tuple[type[SoAIError], str]] = {
        "skill_invalid_package": (
            ValidationError,
            "Import a valid SKILL.md file or a ZIP skill collection. Check the file format and size limits.",
        ),
        "skill_upload_conflict": (
            ConflictError,
            "This upload identity was already used for different bytes. Select the file again to start a new import.",
        ),
        "skill_name_conflict": (
            ConflictError,
            "A skill with this name is already installed. Remove it before importing a replacement.",
        ),
        "skill_library_full": (
            ValidationError,
            "Skill library capacity reached. Remove unused skills and wait for work using removed skills to finish.",
        ),
        "skill_invocation_unavailable": (
            ValidationError,
            "The requested skill is not enabled or does not allow direct invocation. Review this chat's Skills selection.",
        ),
        "skill_selection_conflict": (
            ConflictError,
            "The selection changed elsewhere. Review the current selection before saving your draft.",
        ),
        "skill_import_busy": (
            ServiceUnavailableError,
            "Skill import is busy. Retry the same upload shortly.",
        ),
        "skill_not_found": (
            NotFoundError,
            "The skill or resource is unavailable. Refresh your skill library.",
        ),
        "skill_context_full": (
            ValidationError,
            "Skill instructions do not fit the remaining conversation context. Compact the conversation or select a model with a larger context.",
        ),
    }
    error_type, message = failures[code]
    if reason is not None:
        reason_messages: dict[SkillErrorReason, tuple[SkillErrorCode, str]] = {
            "archive_integrity": (
                "skill_invalid_package",
                "The skill archive is corrupt or incomplete. Download it again and retry with the complete file.",
            ),
            "archive_unsafe": (
                "skill_invalid_package",
                "The skill archive contains unsafe paths, links or conflicting entries. Create a portable archive containing regular files.",
            ),
            "archive_unsupported": (
                "skill_invalid_package",
                "The skill archive uses unsupported encryption or compression. Create an unencrypted ZIP using stored or deflated entries.",
            ),
            "invalid_filename": (
                "skill_invalid_package",
                "Choose a file named SKILL.md or a ZIP skill archive.",
            ),
            "resource_limit": (
                "skill_invalid_package",
                "The skill import exceeds a resource limit. Reduce the archive or remove unused skills before retrying.",
            ),
            "source_conflict": (
                "skill_invalid_package",
                "The collection contains conflicting copies of the same skill. Keep one consistent copy.",
            ),
            "manifest_format": (
                "skill_invalid_package",
                "SKILL.md must contain UTF-8 text with valid plain YAML frontmatter between --- delimiters. Check its format and manifest size limit.",
            ),
            "invalid_field": (
                "skill_invalid_package",
                "A skill manifest field is unsupported, missing or invalid. Check the supported fields and their value types.",
            ),
            "wrapper_name_mismatch": (
                "skill_invalid_package",
                "The enclosing ZIP directory must match the skill name in SKILL.md.",
            ),
            "restriction_unsupported": (
                "skill_invocation_unavailable",
                "This skill uses unsupported restrictive tool syntax. Use explicit canonical SoAI tool names before activating it.",
            ),
            "tool_restricted": (
                "skill_invocation_unavailable",
                "An active skill prohibits this tool. Follow its permitted tool workflow or start a new execution with an appropriate skill selection.",
            ),
            "argument_conflict": (
                "skill_invocation_unavailable",
                "The skill arguments were fixed by the admitted invocation and cannot be replaced. Start a distinct invocation to supply different arguments.",
            ),
            "alias_ambiguous": (
                "skill_invocation_unavailable",
                "This skill alias identifies multiple admitted skills. Invoke an unambiguous qualified skill name.",
            ),
        }
        expected_code, message = reason_messages[reason]
        if code != expected_code:
            raise ValueError("Skill failure reason does not match its error code.")
    details: JSONDict = {"reason": reason} if reason is not None else {}
    if reason == "resource_limit":
        if (
            not field
            or not field.isascii()
            or len(field) > 80
            or not all(character.isalnum() or character in "-_." for character in field)
        ):
            raise ValueError("Skill resource limit requires its resource field.")
        actual = require_int(
            measured, label="Measured skill resource", build_error=ValueError, minimum=0
        )
        maximum = require_int(
            limit, label="Skill resource limit", build_error=ValueError, minimum=0
        )
        if actual <= maximum:
            raise ValueError("Skill resource limit must be exceeded.")
        details.update(measured=actual, limit=maximum)
        message = f"Skill import resource '{field}' exceeds its limit: {actual} > {maximum}. Reduce the archive or remove unused skills before retrying."
    elif measured is not None or limit is not None:
        raise ValueError("Measured limits require a skill resource limit reason.")
    if (
        field is not None
        and field.isascii()
        and 0 < len(field) <= 80
        and all(character.isalnum() or character in "-_." for character in field)
    ):
        details["field"] = field
        if reason == "invalid_field":
            message = f"Skill manifest field '{field}' is unsupported, missing or invalid. Check its name and value type."
    if locations is not None:
        if reason != "source_conflict":
            raise ValueError("Skill source locations require a source conflict reason.")
        details["locations"] = list(locations)
        message = f"Skill identity conflicts at separate source locations: {locations[0]}, {locations[1]}. Keep one consistent copy."
    if source_position is not None:
        if reason != "manifest_format":
            raise ValueError("Skill source positions require a manifest format reason.")
        line, column = source_position
        details["line"] = require_int(
            line, label="Skill source line", build_error=ValueError, minimum=1
        )
        details["column"] = require_int(
            column, label="Skill source column", build_error=ValueError, minimum=1
        )
    error = error_type(message, details=details or None)
    apply_public_error_payload(
        error,
        ErrorPublicPayload(
            code=code,
            message=message,
            details=details or None,
            http_status=error.http_status,
        ),
    )
    return error


def project_skill_package_error(exception: ValidationError) -> SoAIError:
    public = project_specific_public_error(exception)
    if public is not None and public.code == "skill_invalid_package":
        return exception
    details = exception.details or {}
    resource, measured, limit = (
        details.get("archive_resource"),
        details.get("measured"),
        details.get("limit"),
    )
    if isinstance(resource, str) and isinstance(measured, int) and isinstance(limit, int):
        return build_skill_error(
            "skill_invalid_package",
            reason="resource_limit",
            field=resource,
            measured=measured,
            limit=limit,
        )
    if details.get("archive_reason") == "unsupported":
        return build_skill_error("skill_invalid_package", reason="archive_unsupported")
    return build_skill_error("skill_invalid_package")
