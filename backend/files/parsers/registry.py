"""SoAI - File parser registry [backend/files/parsers/registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import override

from core.errors.exceptions import ValidationError
from core.files.extensions.archives import (
    COMPRESSED_EXTENSIONS,
    ISO_EXTENSIONS,
    TAR_EXTENSIONS,
    ZIP_EXTENSIONS,
)
from core.files.extensions.binaries_extensions_archives_and_disk_images import (
    BINARY_EXTENSIONS_ARCHIVES_AND_DISK_IMAGES,
)
from core.files.extensions.binaries_extensions_design_and_fonts import (
    BINARY_EXTENSIONS_DESIGN_AND_FONTS,
)
from core.files.extensions.binaries_extensions_diagnostics_and_profiling import (
    BINARY_EXTENSIONS_DIAGNOSTICS_AND_PROFILING,
)
from core.files.extensions.binaries_extensions_executables import (
    BINARY_EXTENSIONS_EXECUTABLES,
)
from core.files.extensions.binaries_extensions_firmware_and_filesystems import (
    BINARY_EXTENSIONS_FIRMWARE_AND_FILESYSTEMS,
)
from core.files.extensions.binaries_extensions_games_and_roms import (
    BINARY_EXTENSIONS_GAMES_AND_ROMS,
)
from core.files.extensions.binaries_extensions_media_misc import (
    BINARY_EXTENSIONS_MEDIA_MISC,
)
from core.files.extensions.binaries_extensions_packages_and_bundles import (
    BINARY_EXTENSIONS_PACKAGES_AND_BUNDLES,
)
from core.files.extensions.binaries_extensions_storage_and_data import (
    BINARY_EXTENSIONS_STORAGE_AND_DATA,
)
from core.files.extensions.documents import (
    DOCX_EXTENSIONS,
    HTML_EXTENSIONS,
    MOBI_EXTENSIONS,
    ODF_GENERIC_EXTENSIONS,
    ODP_EXTENSIONS,
    ODT_EXTENSIONS,
    PPTX_EXTENSIONS,
)
from core.files.extensions.media import (
    AUDIO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
)
from core.files.extensions.messaging import (
    MESSAGING_EXTENSIONS,
    PLATFORM_DISCORD,
    PLATFORM_FACEBOOK,
    PLATFORM_MSN,
    PLATFORM_SIGNAL,
    PLATFORM_TELEGRAM,
    PLATFORM_WHATSAPP,
)
from core.files.protocols import FileParserProtocol
from core.files.text_extensions import TEXT_EXTENSIONS
from core.files.types import ParsedDocument
from core.imports.availability import module_available
from core.logging.trace import get_logger
from files.parsers.archive_parser import ArchiveParser
from files.parsers.binary_parser import BinaryParser
from files.parsers.blocking_parser import BlockingParser
from files.parsers.media.audio_parser import AudioParser, AudioParserDependencies
from files.parsers.media.image_parser import (
    ImageParser,
    ImageParserConfig,
    ImageParserDependencies,
)
from files.parsers.media.video_parser import VideoParser, VideoParserDependencies
from files.parsers.messaging.detection import detect_messaging_platform
from files.parsers.messaging.discord import DiscordParser
from files.parsers.messaging.facebook import FacebookMessengerParser
from files.parsers.messaging.msn import MSNMessengerParser
from files.parsers.messaging.signal import SignalParser
from files.parsers.messaging.telegram import TelegramParser
from files.parsers.messaging.whatsapp import WhatsAppParser
from files.parsers.rar_parser import RARParser
from files.parsers.registry_dependencies import ParserRegistryDependencies
from files.parsers.spreadsheet import ODS_EXTENSIONS, XLSX_EXTENSIONS
from files.parsers.text import IPYNBParser, TextParser

__all__ = (
    "MessagingParser",
    "create_messaging_parser_registry",
    "create_parser_registry",
)

LOGGER_NAME_FILES_IMAGEPARSER = "SoAI.files.parsers.imageparser"
_TIKA_EXTENSIONS = frozenset(
    (
        "pdf",
        "doc",
        "docx",
        "docm",
        "dotx",
        "dotm",
        "xls",
        "xlsx",
        "xlsm",
        "xltx",
        "xltm",
        "ppt",
        "pptx",
        "pptm",
        "potx",
        "potm",
        "ppsx",
        "ppsm",
        "rtf",
        "odt",
        "ods",
        "odp",
        "odg",
        "odb",
        "odf",
        "odc",
        "odi",
        "odm",
        "epub",
        "mobi",
        "azw",
        "azw3",
        "fb2",
        "eml",
        "msg",
        "mbox",
        "html",
        "htm",
        "xhtml",
        "csv",
        "tsv",
        "xml",
        "json",
        "7z",
        "tar",
        "gz",
        "gzip",
        "bz2",
        "xz",
        "lzma",
        "zst",
        "zstd",
        "iso",
        "udf",
        *ZIP_EXTENSIONS,
    ),
)


def _register_extension_group(
    parsers: dict[str, FileParserProtocol],
    extensions: frozenset[str],
    parser: FileParserProtocol,
) -> None:
    parsers.update(dict.fromkeys(extensions, parser))


def _build_messaging_parser_registry() -> dict[str, BlockingParser]:
    parser_definitions = (
        (PLATFORM_WHATSAPP, WhatsAppParser),
        (PLATFORM_TELEGRAM, TelegramParser),
        (PLATFORM_DISCORD, DiscordParser),
        (PLATFORM_SIGNAL, SignalParser),
        (PLATFORM_FACEBOOK, FacebookMessengerParser),
        (PLATFORM_MSN, MSNMessengerParser),
    )
    return {name: parser_cls() for name, parser_cls in parser_definitions}


def create_messaging_parser_registry() -> dict[str, FileParserProtocol]:
    parsers: dict[str, FileParserProtocol] = dict(_build_messaging_parser_registry())
    return parsers


class MessagingParser(BlockingParser):

    def __init__(self) -> None:
        self._parsers = _build_messaging_parser_registry()

    @override
    def parse_blocking(self, file_path: str) -> ParsedDocument:
        platform = detect_messaging_platform(file_path)
        if platform is None:
            raise ValidationError(f"Not a recognized messaging export format: {file_path}")
        parser = self._parsers.get(platform)
        if parser is None:
            raise ValidationError(f"No parser available for platform: {platform}")
        return parser.parse_blocking(file_path)


def create_parser_registry(
    deps: ParserRegistryDependencies,
) -> dict[str, FileParserProtocol]:
    parsers: dict[str, FileParserProtocol] = {}
    for extensions in (
        _TIKA_EXTENSIONS,
        ODT_EXTENSIONS | ODS_EXTENSIONS | ODP_EXTENSIONS | ODF_GENERIC_EXTENSIONS,
        DOCX_EXTENSIONS | XLSX_EXTENSIONS | PPTX_EXTENSIONS,
        HTML_EXTENSIONS | MOBI_EXTENSIONS | TAR_EXTENSIONS | ISO_EXTENSIONS,
        COMPRESSED_EXTENSIONS,
    ):
        _register_extension_group(parsers, extensions, deps.tika_parser)
    parsers["ipynb"] = IPYNBParser()
    text_parser = TextParser()
    _register_extension_group(parsers, TEXT_EXTENSIONS, text_parser)
    image_supported = (
        module_available("PIL")
        and module_available("rapidocr_onnxruntime")
        and module_available("numpy")
    )
    if image_supported:
        image_parser = ImageParser(
            ImageParserDependencies(
                config=ImageParserConfig(enable_ocr=True),
                preprocessor=deps.image_preprocessor,
                logger=get_logger(LOGGER_NAME_FILES_IMAGEPARSER),
            ),
        )
        heif_extensions = (
            frozenset[str]() if module_available("pi_heif") else frozenset[str]({"heic", "heif"})
        )
        _register_extension_group(
            parsers,
            IMAGE_EXTENSIONS.difference(heif_extensions),
            image_parser,
        )
    transcription_available = module_available("whisper") and module_available("torch")
    audio_parser = AudioParser(
        AudioParserDependencies(
            transcription_runtime=deps.transcription_runtime,
            config=deps.config,
            transcription_available=transcription_available,
        ),
    )
    _register_extension_group(parsers, AUDIO_EXTENSIONS, audio_parser)
    video_parser = VideoParser(
        VideoParserDependencies(
            transcription_runtime=deps.transcription_runtime,
            ocr_runtime=deps.ocr_runtime,
            config=deps.config,
            storage_manager=deps.storage_manager,
            transcription_available=transcription_available,
        ),
    )
    _register_extension_group(parsers, VIDEO_EXTENSIONS, video_parser)
    binary_parser = BinaryParser()
    _register_extension_group(
        parsers,
        BINARY_EXTENSIONS_ARCHIVES_AND_DISK_IMAGES
        | BINARY_EXTENSIONS_DESIGN_AND_FONTS
        | BINARY_EXTENSIONS_DIAGNOSTICS_AND_PROFILING
        | BINARY_EXTENSIONS_EXECUTABLES
        | BINARY_EXTENSIONS_FIRMWARE_AND_FILESYSTEMS
        | BINARY_EXTENSIONS_GAMES_AND_ROMS
        | BINARY_EXTENSIONS_PACKAGES_AND_BUNDLES
        | BINARY_EXTENSIONS_MEDIA_MISC
        | BINARY_EXTENSIONS_STORAGE_AND_DATA,
        binary_parser,
    )
    archive_parser = ArchiveParser(parsers, deps.storage_manager)
    _register_extension_group(parsers, TAR_EXTENSIONS | ZIP_EXTENSIONS, archive_parser)
    if module_available("rarfile"):
        parsers["rar"] = RARParser(parsers, deps.storage_manager)
    messaging_parser = MessagingParser()
    _register_extension_group(parsers, MESSAGING_EXTENSIONS, messaging_parser)
    return parsers
