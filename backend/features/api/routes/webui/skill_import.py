"""SoAI - Bounded staged skill import and receipt recovery [backend/features/api/routes/webui/skill_import.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request

from core.concurrency.cancellation import CancellationToken
from core.concurrency.deadlines import deadline_after
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import (
    StateError,
    ValidationError,
)
from core.filesystem.open_files import open_regular_binary_no_symlink
from core.filesystem.windows_sharing_conflicts import remove_path_with_sharing_retry
from core.logging.trace import get_logger
from core.skills.collection_staging import prepare_skill_collection, remove_skill_collection_staging
from core.skills.errors import build_skill_error, project_skill_package_error
from core.skills.limits import MAX_UPLOAD_BYTES
from core.skills.packages import validate_skill_package
from core.skills.records import SkillPackage, StagedSkillCollection
from core.skills.selection import require_skill_upload_id
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC
from core.types.json import JSONDict
from features.api.routes.upload_streaming_multipart_cleanup import (
    MultipartCleanupResult,
    cleanup_staged_multipart_upload,
)
from features.api.routes.upload_streaming_multipart_models import StreamingStagedPart
from features.api.routes.upload_streaming_reservations import StreamingUploadReservationPurpose
from features.api.routes.upload_streaming_single_file_request import (
    SingleFileUploadRequestSpec,
    stage_single_file_upload_request,
)
from features.api.runtime.context import ApiContext

__all__ = ("import_skill",)

LOGGER_NAME = "SoAI.features.api.skill_import"
_CLEANUP_OPERATION = "skills.import.cleanup"


async def import_skill(
    request: Request, api_context: ApiContext, user_id: int, *, collection: bool = False
) -> JSONDict:
    repository = api_context.dependencies.database_skills
    await repository.library(user_id)
    staged = await stage_single_file_upload_request(
        request,
        api_context=api_context,
        spec=SingleFileUploadRequestSpec(
            subsystem="skills",
            owner=f"skills:{user_id}",
            logger=get_logger(LOGGER_NAME),
            reservation_purpose=StreamingUploadReservationPurpose(
                declared_operation="skills.import.stage",
                chunk_operation="skills.import.stage_chunk",
                declared_details={"user_id": user_id},
                chunk_details={"user_id": user_id},
            ),
            required_fields=frozenset(("upload_id",)),
            allowed_fields=frozenset(("upload_id", "content_type")),
            maximum_bytes=MAX_UPLOAD_BYTES,
        ),
    )
    part = staged.parsed.files[0]
    prepared: list[StagedSkillCollection] = []
    try:
        upload_values = staged.parsed.fields["upload_id"]
        if len(upload_values) != 1:
            raise ValidationError("Provide exactly one skill upload identity.")
        upload_id = require_skill_upload_id(upload_values[0])
        receipt = (
            await repository.import_batch_receipt(user_id, upload_id)
            if collection
            else await repository.import_receipt(user_id, upload_id)
        )
        if receipt is not None:
            if receipt["upload_digest"] != part.content_sha256:
                raise build_skill_error("skill_upload_conflict")
            return receipt
        token = CancellationToken(f"skills.import:{upload_id}")

        def cancel_validation() -> None:
            token.cancel("Skill import request cancelled.")

        try:
            if collection:
                validated = await run_joined_thread_call(
                    _prepare_staged_collection,
                    part,
                    token,
                    task_name=f"skills.import.collection:{upload_id}",
                    retain_resources_until_complete=True,
                    cancelled_result_cleanup=prepared.append,
                    on_cancel=cancel_validation,
                    pool=api_context.dependencies.skill_import_pool,
                    admission_deadline=deadline_after(INTERACTIVE_TIMEOUT_SEC),
                )
                prepared.append(validated)
                return await repository.install_batch(
                    user_id,
                    upload_id,
                    validated,
                    storage_provider=api_context.dependencies.storage_manager,
                )
            package = await run_joined_thread_call(
                _validate_staged_skill,
                part,
                task_name=f"skills.import.validate:{upload_id}",
                retain_resources_until_complete=True,
                pool=api_context.dependencies.skill_import_pool,
                admission_deadline=deadline_after(INTERACTIVE_TIMEOUT_SEC),
            )
            return await repository.install(
                user_id,
                upload_id,
                package,
                storage_provider=api_context.dependencies.storage_manager,
            )
        except TimeoutError as exception:
            raise build_skill_error("skill_import_busy") from exception
    finally:
        cleanup = await run_joined_thread_call(
            _cleanup_import_staging,
            part,
            tuple(prepared),
            task_name="skills.import.cleanup",
            retain_resources_until_complete=True,
        )
        if not cleanup.succeeded:
            log_handled_exception(
                get_logger(LOGGER_NAME),
                StateError("Skill upload staging cleanup failed.", cause=cleanup.first_failure),
                message="Failed to remove skill upload staging data.",
                operation=_CLEANUP_OPERATION,
                level="error",
            )


def _cleanup_import_staging(
    part: StreamingStagedPart, collections: tuple[StagedSkillCollection, ...]
) -> MultipartCleanupResult:
    failed_paths: list[str] = []
    failure: Exception | None = None
    for collection in collections:
        try:
            remove_skill_collection_staging(collection)
        except (OSError, StateError) as exception:
            failed_paths.append(collection.directory)
            if failure is None:
                failure = exception
    cleanup = cleanup_staged_multipart_upload(
        opened_writers=[],
        opened_paths=[part.temp_path],
        remove_file=remove_path_with_sharing_retry,
    )
    return MultipartCleanupResult(
        cleanup.failed_writers,
        (*failed_paths, *cleanup.failed_paths),
        failure or cleanup.first_failure,
    )


def _prepare_staged_collection(
    part: StreamingStagedPart, cancellation: CancellationToken
) -> StagedSkillCollection:
    try:
        return prepare_skill_collection(
            part.temp_path,
            part.original_filename,
            part.size_bytes,
            part.content_sha256,
            cancellation,
        )
    except ValidationError as exception:
        projected = project_skill_package_error(exception)
        if projected is exception:
            raise
        raise projected from exception


def _validate_staged_skill(part: StreamingStagedPart) -> SkillPackage:
    with open_regular_binary_no_symlink(part.temp_path) as source:
        content = source.read(MAX_UPLOAD_BYTES + 1)
    try:
        package = validate_skill_package(content, filename=part.original_filename)
    except ValidationError as exception:
        projected = project_skill_package_error(exception)
        if projected is exception:
            raise
        raise projected from exception
    if len(content) != part.size_bytes or package.upload_digest != part.content_sha256:
        raise StateError("Staged skill upload changed before validation.")
    return package
