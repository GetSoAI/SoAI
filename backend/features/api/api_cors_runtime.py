"""SoAI - API CORS runtime configuration [backend/features/api/api_cors_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from typing import TypedDict

from core.auth.csrf_tokens import SOAI_CSRF_HEADER_NAME
from core.config.numeric import coerce_positive_int
from core.config.protocols import ConfigProtocol
from core.licensing.constants import (
    LICENSING_DRAFT_REVISION_HEADER,
    LICENSING_REQUEST_DIGEST_HEADER,
)
from core.logging.trace import get_logger
from core.types.json import JSONDict
from features.api.middleware.openai_response_metadata import (
    OPENAI_PROCESSING_MS_HEADER_NAME,
    OPENAI_REQUEST_ID_HEADER_NAME,
    OPENAI_VERSION_HEADER_NAME,
)
from features.api.middleware.security.cors import normalize_cors_allowed_origins
from features.api.middleware.server_time import SOAI_SERVER_TIME_HEADER_NAME

__all__ = (
    "CORSMiddlewareConfig",
    "build_cors_runtime_config",
    "cors_runtime_config_to_json",
)

LOGGER_NAME = "SoAI.features.api.api_cors_runtime"


class CORSMiddlewareConfig(TypedDict, total=False):
    allow_methods: Sequence[str]
    allow_headers: Sequence[str]
    allow_credentials: bool
    allow_origin_regex: str
    allow_origins: Sequence[str]
    expose_headers: Sequence[str]
    max_age: int


def build_cors_runtime_config(
    config_obj: ConfigProtocol,
    *,
    log_wildcard_warning: bool,
) -> CORSMiddlewareConfig:
    origins, wildcard_present = normalize_cors_allowed_origins(config_obj)
    allow_credentials = config_obj.get_bool("SERVER.HTTP.CORS.ALLOW_CREDENTIALS") and (
        wildcard_present or bool(origins)
    )
    cors_config: CORSMiddlewareConfig = {
        "allow_methods": ["*"],
        "allow_headers": ["*"],
        "allow_credentials": allow_credentials,
        "expose_headers": [
            SOAI_CSRF_HEADER_NAME,
            SOAI_SERVER_TIME_HEADER_NAME,
            OPENAI_REQUEST_ID_HEADER_NAME,
            OPENAI_VERSION_HEADER_NAME,
            OPENAI_PROCESSING_MS_HEADER_NAME,
            "Content-Disposition",
            LICENSING_DRAFT_REVISION_HEADER,
            LICENSING_REQUEST_DIGEST_HEADER,
        ],
    }
    if wildcard_present:
        if log_wildcard_warning:
            get_logger(LOGGER_NAME).warning(
                "CORS: 'SERVER.HTTP.CORS.ALLOWED_ORIGINS' contains a wildcard ('*'). This keeps CORS fully open. Disable the wildcard and set SERVER.HTTP.CORS.ALLOWED_ORIGINS to explicit domains for stronger protection.",
            )
        cors_config["allow_origin_regex"] = ".*"
    elif origins:
        cors_config["allow_origins"] = list(origins)
    cors_config["max_age"] = coerce_positive_int(
        config_obj.get_int("SERVER.HTTP.CORS.MAX_AGE_SEC"),
        default=3600,
        minimum=0,
    )
    return cors_config


def cors_runtime_config_to_json(cors_config: CORSMiddlewareConfig) -> JSONDict:
    result: JSONDict = {}
    if "allow_methods" in cors_config:
        result["allow_methods"] = [str(item) for item in cors_config["allow_methods"]]
    if "allow_headers" in cors_config:
        result["allow_headers"] = [str(item) for item in cors_config["allow_headers"]]
    if "allow_credentials" in cors_config:
        result["allow_credentials"] = bool(cors_config["allow_credentials"])
    if "allow_origin_regex" in cors_config:
        result["allow_origin_regex"] = str(cors_config["allow_origin_regex"])
    if "allow_origins" in cors_config:
        result["allow_origins"] = [str(item) for item in cors_config["allow_origins"]]
    if "expose_headers" in cors_config:
        result["expose_headers"] = [str(item) for item in cors_config["expose_headers"]]
    if "max_age" in cors_config:
        result["max_age"] = int(cors_config["max_age"])
    return result
