"""SoAI - Shared media parsing composition [backend/app/composition/build_media_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.media_parsing_services import MediaParsingServices
from core.bootstrap.tesseract_runtime import ensure_tesseract_runtime_installed
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import StateError
from core.hardware.protocols_storage import StorageManagerProtocol
from core.ipc.managed_worker import ManagedIpcWorker
from core.logging.trace import get_logger
from core.media.config import resolve_media_parsing_config
from core.media.image_preprocessing import (
    ImagePreprocessor,
    ImagePreprocessorConfig,
    ImagePreprocessorDependencies,
)
from core.media.ocr_engine import configure_tesseract_runtime
from core.media.ocr_gateway import OcrGateway, OcrGatewayDependencies
from core.media.opencv_backend import create_optional_opencv_api
from core.media.transcription_gateway import (
    TranscriptionGateway,
    TranscriptionGatewayDependencies,
)
from core.media.transcription_runtime import (
    TranscriptionRuntime,
    TranscriptionRuntimeDependencies,
)
from core.meta.paths import get_repo_root
from core.runtime.protocols import RuntimeFlagsViewProtocol
from files.parsers.document import TikaParser, TikaParserDependencies
from files.parsers.document_ocr import (
    DocumentOcrCoordinator,
    DocumentOcrCoordinatorDependencies,
)
from files.parsers.document_reading import build_document_reading_pipeline
from files.parsers.registry import create_parser_registry
from files.parsers.registry_dependencies import ParserRegistryDependencies
from files.parsers.tika_runtime import TikaRuntime, TikaRuntimeDependencies
from mcp.tools.read_audio_service import ReadAudioService, ReadAudioServiceDependencies

__all__ = ("build_media_parsing_services",)

LOGGER_NAME = "SoAI.app.composition.build_media_parsing"
IMAGE_PREPROCESSOR_LOGGER_NAME = "SoAI.files.parsers.imagepreprocessing"
TIKA_RUNTIME_LOGGER_NAME = "SoAI.files.parsers.tika_runtime"
DOCUMENT_OCR_LOGGER_NAME = "SoAI.files.parsers.document_ocr"


def build_media_parsing_services(
    *,
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    storage_manager: StorageManagerProtocol,
) -> MediaParsingServices:
    repo_root_path = get_repo_root()
    logger = get_logger(LOGGER_NAME)
    try:
        tesseract_executable, tesseract_data = ensure_tesseract_runtime_installed(repo_root_path)
    except (OSError, StateError) as exception:
        logger.warning(
            "Managed Tesseract OCR is unavailable: %s. Raster-only document OCR will report unavailable.",
            type(exception).__name__,
        )
    else:
        configure_tesseract_runtime(tesseract_executable, tesseract_data)
    media_config = resolve_media_parsing_config(config)
    transcription_gateway = TranscriptionGateway(
        TranscriptionGatewayDependencies(
            config=config,
            runtime_flags=runtime_flags,
            worker_builder=ManagedIpcWorker,
        ),
    )
    transcription_runtime = TranscriptionRuntime(
        TranscriptionRuntimeDependencies(
            config=config,
            gateway=transcription_gateway,
            chunk_seconds=media_config.audio_chunk_seconds,
            audio_extraction_timeout_seconds=media_config.audio_extraction_timeout_sec,
            temp_reservation_safety_multiplier=(media_config.temp_reservation_safety_multiplier),
            storage_manager=storage_manager,
        ),
    )
    ocr_runtime = OcrGateway(
        OcrGatewayDependencies(
            config=config,
            worker_builder=ManagedIpcWorker,
        ),
    )
    opencv_api = create_optional_opencv_api()
    image_preprocessor = (
        None
        if opencv_api is None
        else ImagePreprocessor(
            ImagePreprocessorDependencies(
                opencv_api=opencv_api,
                config=ImagePreprocessorConfig(),
                logger=get_logger(IMAGE_PREPROCESSOR_LOGGER_NAME),
            ),
        )
    )
    tika_runtime = TikaRuntime(
        TikaRuntimeDependencies(
            repo_root_path=repo_root_path,
            logger=get_logger(TIKA_RUNTIME_LOGGER_NAME),
        ),
    )
    tika_parser = TikaParser(TikaParserDependencies(runtime=tika_runtime))
    parser_registry = create_parser_registry(
        ParserRegistryDependencies(
            storage_manager=storage_manager,
            transcription_runtime=transcription_runtime,
            ocr_runtime=ocr_runtime,
            tika_parser=tika_parser,
            image_preprocessor=image_preprocessor,
            config=config,
        ),
    )
    document_ocr = DocumentOcrCoordinator(
        DocumentOcrCoordinatorDependencies(
            preprocessor=image_preprocessor,
            logger=get_logger(DOCUMENT_OCR_LOGGER_NAME),
        ),
    )
    document_reader = build_document_reading_pipeline(document_ocr)
    return MediaParsingServices(
        tika_runtime=tika_runtime,
        transcription_runtime=transcription_runtime,
        ocr_runtime=ocr_runtime,
        parser_registry=parser_registry,
        document_reader=document_reader,
        read_audio_service=ReadAudioService(
            ReadAudioServiceDependencies(
                config=config,
                transcription_runtime=transcription_runtime,
            ),
        ),
    )
