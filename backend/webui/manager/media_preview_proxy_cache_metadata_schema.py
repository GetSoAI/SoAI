"""SoAI - WebUI media preview cache metadata schema V1 [backend/webui/manager/media_preview_proxy_cache_metadata_schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import pydantic_core
from pydantic import BaseModel, ConfigDict, Field

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.meta.soai_v1_contract import WEBUI_MEDIA_PREVIEW_CACHE_METADATA_SCHEMA_VERSION
from core.types.json import JSONDict
from webui.manager.media_preview_cache_metadata_runner import (
    upgrade_media_preview_cache_metadata_payload_to_current,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = (
    "MediaPreviewCacheMetadataV1",
    "build_media_preview_cache_metadata_v1",
    "try_parse_media_preview_cache_metadata_v1",
)

LOGGER_NAME = "SoAI.webui.manager.media_preview_proxy_cache_metadata_schema"
OPERATION = "webui.media.proxy.cache.metadata_schema"


class MediaPreviewCacheMetadataV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=WEBUI_MEDIA_PREVIEW_CACHE_METADATA_SCHEMA_VERSION)
    source_url: str
    final_url: str
    content_type: str
    bytes_written: int
    declared_content_length: int | None


def build_media_preview_cache_metadata_v1(
    *,
    source_url: str,
    final_url: str,
    content_type: str,
    bytes_written: int,
    declared_content_length: int | None,
) -> JSONDict:
    model = MediaPreviewCacheMetadataV1(
        schema_version=WEBUI_MEDIA_PREVIEW_CACHE_METADATA_SCHEMA_VERSION,
        source_url=str(source_url),
        final_url=str(final_url),
        content_type=str(content_type),
        bytes_written=int(bytes_written),
        declared_content_length=(
            declared_content_length
            if declared_content_length is None
            else int(declared_content_length)
        ),
    )
    return model.model_dump()


def try_parse_media_preview_cache_metadata_v1(
    payload: JSONDict,
) -> MediaPreviewCacheMetadataV1 | None:
    logger: LoggerProtocol = get_logger(LOGGER_NAME)
    try:
        payload, _ = upgrade_media_preview_cache_metadata_payload_to_current(payload, logger=logger)
    except (ValidationError, TypeError, ValueError) as exception:
        log_handled_exception(
            logger,
            exception,
            message="Invalid media preview cache metadata schema (cache miss).",
            operation=OPERATION,
            level="warning",
        )
        return None
    if payload.get("schema_version") != WEBUI_MEDIA_PREVIEW_CACHE_METADATA_SCHEMA_VERSION:
        return None
    try:
        return MediaPreviewCacheMetadataV1.model_validate(payload)
    except (pydantic_core.ValidationError, TypeError, ValueError) as exception:
        log_handled_exception(
            logger,
            exception,
            message="Invalid media preview cache metadata schema (cache miss).",
            operation=OPERATION,
            level="warning",
        )
        return None
