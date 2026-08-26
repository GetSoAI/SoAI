"""SoAI - Shared system about-information loader [backend/features/api/runtime/system_about.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import platform

from core.errors.exception_logging import log_exception
from core.errors.exceptions import NotFoundError, SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.licensing.legal_documents import load_licensing_document
from core.licensing.policy import EditionLicensingPolicy
from core.logging.trace import get_logger
from core.meta.versioning import get_core_version
from features.api.runtime.project_root_files import read_text_file_from_project_root

__all__ = (
    "SYSTEM_DESCRIPTION",
    "SYSTEM_LICENSE_NAME",
    "load_public_system_info_payload",
    "load_system_info_payload",
    "load_system_license_payload",
    "load_system_requirements_text",
)

OPERATION_FEATURES_API_RUNTIME_SYSTEM_ABOUT_READ_SYSTEM_TEXT_FILE = (
    "features.api.runtime.system_about.read_system_text_file"
)


LOGGER_NAME = "SoAI.features.api.system_about"


SYSTEM_DESCRIPTION = "SoAI is a unified backend for running local and remote AI models, providing a standardized API for inference, hardware management, and dynamic model orchestration."
SYSTEM_LICENSE_NAME = "LicenseRef-SoAI-Source-1.0"


def _read_system_text_file(
    *,
    candidate_files: tuple[str, ...],
    not_found_message: str,
    failure_message: str,
    operation: str,
    failure_log_message: str,
) -> str:
    logger = get_logger(LOGGER_NAME)
    try:
        _resolved_file, text = read_text_file_from_project_root(candidate_files)
    except NotFoundError as exception:
        raise NotFoundError(
            not_found_message,
            cause=exception,
            operation=operation,
        ) from exception
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=failure_log_message,
            operation=OPERATION_FEATURES_API_RUNTIME_SYSTEM_ABOUT_READ_SYSTEM_TEXT_FILE,
            level="error",
        )
        raise SoAIError(
            failure_message,
            cause=exception,
            operation=operation,
        ) from exception
    return text


def load_system_license_payload(
    *,
    project_root: str,
    policy: EditionLicensingPolicy,
) -> dict[str, int | str]:
    document = load_licensing_document(
        project_root,
        policy.controlling_license_relative_path,
        policy.legal_catalog_relative_paths,
    )
    return {
        "schema_version": 1,
        "edition": policy.edition,
        "document_name": policy.controlling_license_name,
        "fingerprint": document.fingerprint,
        "license_text": document.content.decode("utf-8"),
    }


def load_system_requirements_text() -> str:
    return _read_system_text_file(
        candidate_files=("requirements.txt",),
        not_found_message="requirements.txt file not found.",
        failure_message="Failed to read requirements.txt file.",
        operation="api_system.load_system_requirements_text",
        failure_log_message="Failed to read requirements.txt file",
    )


def load_public_system_info_payload() -> dict[str, str]:
    return {
        "license_name": SYSTEM_LICENSE_NAME,
        "description": SYSTEM_DESCRIPTION,
    }


def load_system_info_payload(
    *,
    base_dir: str | None = None,
    system_data_path: str | None = None,
) -> dict[str, str]:
    _ = base_dir
    _ = system_data_path
    payload: dict[str, str] = {
        "soai_version": get_core_version(),
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "license_name": SYSTEM_LICENSE_NAME,
        "description": SYSTEM_DESCRIPTION,
    }
    return payload
