"""SoAI - Upload publication acceptance and cleanup ownership [backend/files/upload_acceptance.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.concurrency.cancellation_cleanup import wait_for_task_completion
from core.database.operation_status import DatabaseOperationStatusValue
from core.database.protocols import DatabaseOperationStatusProtocol
from core.database.write_acceptance import completed_write_outcome
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exceptions import SoAIError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.protocols import DatabaseFilesProtocol
from core.files.upload_cleanup import cleanup_upload_artifacts
from core.state.errors import DatabaseWriteAcceptanceUnresolvedError

__all__ = ("UploadAcceptance",)


@dataclass(slots=True)
class UploadAcceptance:
    database_files: DatabaseFilesProtocol
    database_operation_status: DatabaseOperationStatusProtocol
    temporary_path: str
    user_id: int | None
    api_key_id: str | None
    file_id: str = ""
    permanent_path: str | None = None
    published: bool = False
    record_accepted: bool = False
    database_write_task: asyncio.Task[bool] | None = None

    async def cleanup(self) -> SoAIError | None:
        may_remove = self.published and not self.record_accepted
        acceptance_error: SoAIError | None = None
        if self.database_write_task is not None:
            await wait_for_task_completion(
                self.database_write_task, retain_resources_until_complete=True
            )
            try:
                outcome = await completed_write_outcome(
                    self.database_write_task, self.database_operation_status
                )
                self.record_accepted = outcome is DatabaseOperationStatusValue.COMMITTED
                may_remove = self.published and outcome in {
                    DatabaseOperationStatusValue.FAILED,
                    DatabaseOperationStatusValue.SKIPPED,
                    DatabaseOperationStatusValue.NOT_COMMITTED,
                }
                if may_remove:
                    record = await self.database_files.get_file_info_with_path(
                        self.file_id,
                        enforce_owner=True,
                        user_id=self.user_id,
                        api_key_id=self.api_key_id,
                    )
                    may_remove = record is None or record.get("file_path") != self.permanent_path
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                may_remove = False
                acceptance_error = DatabaseWriteAcceptanceUnresolvedError(
                    "Upload acceptance is unresolved; stored bytes have been retained.",
                    cause=exception,
                    details=(
                        {"file_id": self.file_id, **(exception.details or {})}
                        if isinstance(exception, SoAIError)
                        else {"file_id": self.file_id}
                    ),
                )
        try:
            await cleanup_upload_artifacts(
                temp_path=self.temporary_path,
                permanent_path=self.permanent_path if may_remove else None,
            )
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            return coerce_to_soai_error(exception, operation="files.upload_acceptance.cleanup")
        return acceptance_error
