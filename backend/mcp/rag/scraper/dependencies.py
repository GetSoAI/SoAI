"""SoAI - MCP web scraper dependencies [backend/mcp/rag/scraper/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import httpx2
from charset_normalizer import from_bytes

from core.browser_adblock.protocols import EasyListAdblockServiceProtocol
from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError
from core.files.mime_detection import create_mime_detector
from core.files.protocols import FileParserProtocol
from core.hardware.protocols_storage import StorageManagerProtocol
from core.logging.trace import get_logger
from core.runtime.protocols import RuntimeFlagsViewProtocol
from mcp.rag.scraper.internal_protocols import (
    CharsetDetectorProtocol,
    MagicDetectorProtocol,
)

__all__ = (
    "WebContentFetcherDependencies",
    "build_web_content_fetcher_dependencies",
    "load_charset_detector",
    "load_magic_detector",
    "resolve_html_parser",
)

LOGGER_NAME = "SoAI.mcp.rag.dependencies"


@dataclass(frozen=True, slots=True)
class WebContentFetcherDependencies:
    http_client: httpx2.AsyncClient
    config: ConfigProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    storage_manager: StorageManagerProtocol
    parser_registry: dict[str, FileParserProtocol]
    adblock_service: EasyListAdblockServiceProtocol | None
    charset_detector: CharsetDetectorProtocol
    magic_detector: MagicDetectorProtocol
    html_parser: str

    def __post_init__(self) -> None:
        require_dependencies(
            owner="WebContentFetcherDependencies",
            charset_detector=self.charset_detector,
            config=self.config,
            html_parser=self.html_parser,
            http_client=self.http_client,
            magic_detector=self.magic_detector,
            parser_registry=self.parser_registry,
            runtime_flags=self.runtime_flags,
            storage_manager=self.storage_manager,
        )
        if not isinstance(self.html_parser, str) or not self.html_parser.strip():
            raise ValidationError(
                "WebContentFetcherDependencies.html_parser must be a non-empty string.",
            )
        if not isinstance(self.parser_registry, dict) or not self.parser_registry:
            raise ValidationError(
                "WebContentFetcherDependencies.parser_registry must be a non-empty mapping.",
            )


def resolve_html_parser() -> str:
    logger = get_logger(LOGGER_NAME)
    parser = "html.parser"
    logger.debug("BeautifulSoup will use '%s' parser for HTML parsing", parser)
    return parser


def load_charset_detector() -> CharsetDetectorProtocol:
    return from_bytes


def load_magic_detector() -> MagicDetectorProtocol:
    logger = get_logger(LOGGER_NAME)
    detector = create_mime_detector()
    from_buffer = detector.from_buffer
    if not callable(from_buffer):
        logger.debug("Failed to initialize local MIME detector.")
        raise ValidationError("Failed to initialize local MIME detector.")
    return detector


def build_web_content_fetcher_dependencies(
    http_client: httpx2.AsyncClient,
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    storage_manager: StorageManagerProtocol,
    parser_registry_factory: Callable[[], dict[str, FileParserProtocol]],
    adblock_service: EasyListAdblockServiceProtocol | None = None,
) -> WebContentFetcherDependencies:
    if http_client is None:
        raise ValidationError("HTTP client is required for web fetcher.")
    if config is None:
        raise ValidationError("Config is required for web fetcher.")
    if runtime_flags is None:
        raise ValidationError("Runtime flags service is required for web fetcher.")
    if storage_manager is None:
        raise ValidationError("Storage manager is required for web fetcher.")
    if parser_registry_factory is None:
        raise ValidationError("Parser registry factory is required for web fetcher.")
    return WebContentFetcherDependencies(
        http_client=http_client,
        config=config,
        runtime_flags=runtime_flags,
        storage_manager=storage_manager,
        parser_registry=parser_registry_factory(),
        adblock_service=adblock_service,
        charset_detector=load_charset_detector(),
        magic_detector=load_magic_detector(),
        html_parser=resolve_html_parser(),
    )
