"""SoAI - Model parameter availability and application errors [backend/core/models/parameter_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ServiceUnavailableError, StateError
from core.errors.payload import ErrorPublicPayload
from core.errors.public_projection import apply_public_error_payload

__all__ = (
    "MODEL_PARAMETERS_APPLY_FAILED_CODE",
    "MODEL_PARAMETER_SCHEMA_BUSY_REASON",
    "MODEL_PARAMETER_SCHEMA_UNAVAILABLE_CODE",
    "MODEL_PARAMETER_SCHEMA_UNREGISTERED_REASON",
    "ModelParameterSchemaUnavailableError",
    "ModelParametersApplyFailedError",
    "build_model_parameter_schema_unavailable_error",
    "build_model_parameters_apply_failed_error",
)

MODEL_PARAMETER_SCHEMA_UNAVAILABLE_CODE = "model_parameter_schema_unavailable"
MODEL_PARAMETER_SCHEMA_BUSY_REASON = "plugin_operation_in_progress"
MODEL_PARAMETER_SCHEMA_UNREGISTERED_REASON = "plugin_unregistered"
MODEL_PARAMETERS_APPLY_FAILED_CODE = "model_parameters_apply_failed"


class ModelParameterSchemaUnavailableError(ServiceUnavailableError):
    code: str | int = MODEL_PARAMETER_SCHEMA_UNAVAILABLE_CODE


class ModelParametersApplyFailedError(StateError):
    code: str | int = MODEL_PARAMETERS_APPLY_FAILED_CODE
    http_status = 500


def build_model_parameter_schema_unavailable_error(
    plugin_name: str, *, operation_in_progress: bool
) -> ModelParameterSchemaUnavailableError:
    if operation_in_progress:
        reason = MODEL_PARAMETER_SCHEMA_BUSY_REASON
        public_message = "Model parameters are temporarily unavailable while a plugin operation is in progress. Retry in a moment."
    else:
        reason = MODEL_PARAMETER_SCHEMA_UNREGISTERED_REASON
        public_message = "Model parameters are unavailable because the plugin backend is not loaded. Start or repair the plugin, then retry."
    details = {"plugin": plugin_name, "reason": reason}
    error = ModelParameterSchemaUnavailableError(
        f"Parameter schema for plugin '{plugin_name}' is not registered.", details=details
    )
    apply_public_error_payload(
        error,
        ErrorPublicPayload(
            code=MODEL_PARAMETER_SCHEMA_UNAVAILABLE_CODE,
            message=public_message,
            http_status=error.http_status,
            details=details,
        ),
    )
    return error


def build_model_parameters_apply_failed_error(universal_id: str) -> ModelParametersApplyFailedError:
    error = ModelParametersApplyFailedError(
        f"Parameters for model '{universal_id}' were saved, but change notification failed.",
        details={"universal_id": universal_id},
    )
    apply_public_error_payload(
        error,
        ErrorPublicPayload(
            code=MODEL_PARAMETERS_APPLY_FAILED_CODE,
            message="Parameters were saved, but SoAI could not apply them to the running model. Refresh to review the saved values and reload the model to apply them.",
            http_status=error.http_status,
        ),
    )
    return error
