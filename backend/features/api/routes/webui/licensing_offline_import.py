"""SoAI - Offline entitlement multipart import [backend/features/api/routes/webui/licensing_offline_import.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from uuid import uuid4

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import Request

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.filesystem.open_files import open_regular_binary_no_symlink
from core.licensing.constants import (
    MAX_SIGNED_DOCUMENT_BYTES,
    OFFLINE_ENTITLEMENT_FILENAME_SUFFIX,
    OFFLINE_ENTITLEMENT_MEDIA_TYPE,
)
from core.licensing.license_acceptance import require_current_license_acceptance
from core.licensing.offline_entitlement_validation import (
    OfflineEntitlementBinding,
    validate_offline_entitlement,
)
from core.logging.trace import get_logger
from core.timing.epoch import epoch_ms
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX
from features.api.routes.upload_streaming_multipart_cleanup import (
    cleanup_staged_multipart_upload,
)
from features.api.routes.upload_streaming_reservations import (
    StreamingUploadReservationPurpose,
)
from features.api.routes.upload_streaming_single_file_request import (
    SingleFileUploadRequestSpec,
    stage_single_file_upload_request,
)
from features.api.runtime.context import ApiContext

_ACCEPTED_MEDIA_TYPES = frozenset(
    (
        None,
        "application/json",
        "application/octet-stream",
        OFFLINE_ENTITLEMENT_MEDIA_TYPE,
    )
)
_FIELDS = frozenset(("draft_revision", "content_type"))
LOGGER_NAME = "SoAI.features.api.licensing_offline_import"
_CLEANUP_OPERATION = "features.api.routes.webui.licensing_offline_import.cleanup_staging"


async def import_offline_entitlement(
    request: Request,
    api_context: ApiContext,
    *,
    disposition: str,
) -> None:
    staged = await stage_single_file_upload_request(
        request,
        api_context=api_context,
        spec=SingleFileUploadRequestSpec(
            subsystem="licensing_offline_import",
            owner="licensing_offline_import",
            logger=get_logger(LOGGER_NAME),
            reservation_purpose=StreamingUploadReservationPurpose(
                declared_operation="licensing.offline_import.stage",
                chunk_operation="licensing.offline_import.stage_chunk",
                declared_details={"purpose": "offline_entitlement"},
                chunk_details={"purpose": "offline_entitlement"},
            ),
            required_fields=frozenset(("draft_revision",)),
            allowed_fields=_FIELDS,
            maximum_bytes=MAX_SIGNED_DOCUMENT_BYTES,
        ),
    )
    part = staged.parsed.files[0]
    try:
        if not part.original_filename.endswith(OFFLINE_ENTITLEMENT_FILENAME_SUFFIX):
            raise ValidationError("Offline entitlement filename is invalid.")
        if part.content_type not in _ACCEPTED_MEDIA_TYPES:
            raise ValidationError("Offline entitlement media type is invalid.")
        _validate_content_type_metadata(staged.parsed.fields, part.content_type)
        revision = _draft_revision(staged.parsed.fields)
        with open_regular_binary_no_symlink(part.temp_path) as source:
            content = source.read(MAX_SIGNED_DOCUMENT_BYTES + 1)
        if len(content) > MAX_SIGNED_DOCUMENT_BYTES:
            raise ValidationError("Offline entitlement exceeds its V1 size limit.")
        await _validate_and_persist(api_context, revision, content, disposition)
    finally:
        cleanup = cleanup_staged_multipart_upload(
            opened_writers=[],
            opened_paths=[part.temp_path],
        )
        if not cleanup.succeeded:
            cleanup_error = StateError(
                "Offline entitlement staging cleanup failed.",
                operation=_CLEANUP_OPERATION,
                cause=cleanup.first_failure,
                details={"failed_path_count": len(cleanup.failed_paths)},
            )
            log_handled_exception(
                get_logger(LOGGER_NAME),
                cleanup_error,
                message="Failed to remove offline entitlement staging data.",
                operation=_CLEANUP_OPERATION,
                level="error",
            )


async def _validate_and_persist(
    api_context: ApiContext,
    draft_revision: int,
    content: bytes,
    disposition: str,
) -> None:
    dependencies = api_context.dependencies
    draft = await dependencies.database_licensing_wizard.read_wizard_draft(
        dependencies.licensing_policy.edition
    )
    require_current_license_acceptance(
        draft,
        dependencies.licensing_service.controlling_license_fingerprint,
    )
    if not dependencies.licensing_policy.product_access_required(draft["declaration"]):
        raise ValidationError("Licensing product access is not required.")
    offline_request = await dependencies.database_licensing.offline_request()
    if offline_request is None:
        raise ValidationError("Offline activation request is unavailable.")
    active = await dependencies.database_licensing.active_document()
    catalog = dependencies.licensing_trust_material.require_catalog()
    root_public = catalog.root_public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    validated = validate_offline_entitlement(
        content,
        root_public,
        OfflineEntitlementBinding(
            edition=dependencies.licensing_policy.edition,
            instance_id=offline_request.instance_id,
            deployment_public_key=offline_request.deployment_public_key,
            customer_request_digest=offline_request.request_digest,
            current_deployment_id=active.deployment_id if active is not None else None,
            current_generation=active.generation if active is not None else None,
            current_document=active.canonical_content if active is not None else None,
        ),
    )
    await dependencies.database_licensing.accept_offline_entitlement(
        operation_id=str(uuid4()),
        expected_draft_revision=draft_revision,
        edition=dependencies.licensing_policy.edition,
        document_digest=validated.document_digest,
        canonical_content=validated.canonical_document,
        entitlement_type=validated.entitlement_type,
        allocation_id=validated.allocation_id,
        license_id=validated.license_id,
        deployment_id=validated.deployment_id,
        generation=validated.generation,
        root_snapshot=validated.root_snapshot,
        accepted_at_ms=epoch_ms(),
        disposition=disposition,
    )


def _draft_revision(fields: dict[str, tuple[str, ...]]) -> int:
    values = fields.get("draft_revision")
    if values is None or len(values) != 1 or not values[0].isascii() or not values[0].isdigit():
        raise ValidationError("Offline entitlement draft revision is invalid.")
    revision = int(values[0])
    if revision < 1 or revision > JAVASCRIPT_SAFE_INTEGER_MAX:
        raise ValidationError("Offline entitlement draft revision is invalid.")
    return revision


def _validate_content_type_metadata(
    fields: dict[str, tuple[str, ...]],
    part_content_type: str | None,
) -> None:
    values = fields.get("content_type")
    if values is None:
        return
    if len(values) != 1:
        raise ValidationError("Offline entitlement content type metadata is invalid.")
    normalized = values[0].strip().lower()
    if not normalized or normalized != part_content_type:
        raise ValidationError("Offline entitlement content type metadata is contradictory.")


__all__ = ("import_offline_entitlement",)
