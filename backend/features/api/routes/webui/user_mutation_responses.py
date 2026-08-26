"""SoAI - Public WebUI identity mutation status projection [backend/features/api/routes/webui/user_mutation_responses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import Literal, Never

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse

from core.auth.cookies import (
    determine_secure_cookie,
    resolve_webui_cookie_names,
    set_auth_cookie_record,
)
from core.auth.jwt_claims import AccessTokenRecord
from core.errors.exceptions import ApiError, ConflictError, StateError
from core.runtime.proxy_headers import resolve_request_scheme
from core.timing.constants import CONTROL_TIMEOUT_SEC
from core.types.json import JSONDict
from core.users.identity_mutation_records import (
    IdentityMutationBinding,
    IdentityMutationRecord,
)
from core.users.protocols_identity_mutations import DatabaseUserMutationsProtocol
from features.api.routes.webui.users_common import serialize_user_response
from features.api.runtime.context import ApiContext


def _identity_mutation_failure_status(code: str) -> int:
    if code in {"incorrect_current_password", "username_unchanged"}:
        return status.HTTP_422_UNPROCESSABLE_CONTENT
    if code in {
        "username_conflict",
        "operation_id_conflict",
        "user_state_conflict",
        "identity_mutation_deadline_exceeded",
        "identity_mutation_cancelled",
        "identity_mutation_not_committed",
        "session_rotation_window_unavailable",
    }:
        return status.HTTP_409_CONFLICT
    if code in {"identity_mutation_time_invalid", "identity_mutation_session_collision"}:
        return status.HTTP_503_SERVICE_UNAVAILABLE
    return status.HTTP_500_INTERNAL_SERVER_ERROR


def raise_identity_mutation_failure(
    code: str,
    operation_id: str,
) -> Never:
    raise ApiError(
        "Identity mutation did not complete.",
        code=code,
        http_status=_identity_mutation_failure_status(code),
        details={"operation_id": operation_id},
    )


async def record_identity_mutation_failure(
    database_user_mutations: DatabaseUserMutationsProtocol,
    binding: IdentityMutationBinding,
    code: str,
) -> Literal[True]:
    try:
        record = await database_user_mutations.record_failure(
            binding,
            error_code=code,
            trace_id=None,
        )
    except ConflictError:
        raise_identity_mutation_failure("operation_id_conflict", binding.operation_id)
    if record.status == "committed":
        return True
    if record.error_code is None:
        raise StateError("Failed identity mutation record is missing its error code.")
    raise_identity_mutation_failure(record.error_code, binding.operation_id)


async def read_identity_mutation(
    database_user_mutations: DatabaseUserMutationsProtocol,
    binding: IdentityMutationBinding,
) -> IdentityMutationRecord | None:
    try:
        return await asyncio.wait_for(
            database_user_mutations.read(binding),
            timeout=CONTROL_TIMEOUT_SEC,
        )
    except TimeoutError as exception:
        raise ApiError(
            "Identity mutation status is temporarily unavailable.",
            code="identity_mutation_result_unknown",
            http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"operation_id": binding.operation_id},
            cause=exception,
        ) from exception
    except ConflictError:
        raise_identity_mutation_failure("operation_id_conflict", binding.operation_id)


async def has_terminal_identity_mutation(
    database_user_mutations: DatabaseUserMutationsProtocol,
    binding: IdentityMutationBinding,
) -> bool:
    record = await read_identity_mutation(database_user_mutations, binding)
    if record is None:
        return False
    if record.status == "failed" and record.error_code is not None:
        raise_identity_mutation_failure(record.error_code, binding.operation_id)
    return True


def prepare_identity_mutation_response(
    *,
    request: Request,
    api_context: ApiContext,
    operation_id: str,
    user: JSONDict,
    replacement_token: AccessTokenRecord | None,
    source_csrf_token: str | None,
) -> Response:
    response = JSONResponse(
        content={
            "operation_id": operation_id,
            "user": serialize_user_response(api_context, user),
        },
    )
    if (replacement_token is None) != (source_csrf_token is None):
        raise StateError("Identity mutation response session state is incomplete.")
    if replacement_token is not None and source_csrf_token is not None:
        primary_secret = api_context.dependencies.auth_config.primary_signing_secret
        if primary_secret is None:
            raise StateError("Authentication signing key is unavailable.")
        set_auth_cookie_record(
            response,
            api_context.dependencies.config,
            replacement_token,
            cookie_names=resolve_webui_cookie_names(resolve_request_scheme(request)),
            secret_key=primary_secret,
            secure_cookie=determine_secure_cookie(
                api_context.dependencies.config,
                request_scheme=resolve_request_scheme(request),
            ),
            csrf_token=source_csrf_token,
        )
    response.headers["Cache-Control"] = "no-store"
    return response


def serialize_identity_mutation_record(record: IdentityMutationRecord) -> JSONDict:
    if record.status == "failed":
        result: JSONDict = {
            "status": "failed",
            "operation_id": record.binding.operation_id,
            "operation_type": record.binding.operation_type,
            "error_code": record.error_code,
        }
        if record.trace_id is not None:
            result["trace_id"] = record.trace_id
        return result
    if record.binding.operation_type == "username_rename":
        operation_result: JSONDict = {
            "target_user_id": record.binding.target_user_id,
            "previous_username": record.previous_username,
            "new_username": record.new_username,
            "identity_revision": record.new_identity_revision,
        }
    else:
        operation_result = {
            "target_user_id": record.binding.target_user_id,
            "previous_password_revision": record.previous_password_revision,
            "new_password_revision": record.new_password_revision,
        }
    return {
        "status": "committed",
        "operation_id": record.binding.operation_id,
        "operation_type": record.binding.operation_type,
        "result": operation_result,
    }


def serialize_missing_identity_mutation(operation_id: str) -> JSONDict:
    return {"status": "not_found", "operation_id": operation_id}


__all__ = (
    "has_terminal_identity_mutation",
    "prepare_identity_mutation_response",
    "raise_identity_mutation_failure",
    "read_identity_mutation",
    "record_identity_mutation_failure",
    "serialize_identity_mutation_record",
    "serialize_missing_identity_mutation",
)
