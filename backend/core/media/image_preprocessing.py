"""SoAI - Image preprocessing strategies for OCR enhancement [backend/core/media/image_preprocessing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import StandardLogger

if TYPE_CHECKING:
    from core.media.opencv_api import OpenCVApi

__all__ = (
    "ImagePreprocessor",
    "ImagePreprocessorConfig",
    "ImagePreprocessorDependencies",
)

OPERATION_FILES_IMAGE_PREPROCESSING_DETECT_COMPLEXITY = (
    "files.image_preprocessing.detect_complexity"
)
OPERATION_FILES_IMAGE_PREPROCESSING_NORMALIZE_IMAGE = "files.image_preprocessing.normalize_image"
OPERATION_FILES_IMAGE_PREPROCESSING_PREPROCESS_COMPLEX_STRATEGY = (
    "files.image_preprocessing.preprocess_complex.strategy"
)
OPERATION_FILES_IMAGE_PREPROCESSING_PREPROCESS_SIMPLE = (
    "files.image_preprocessing.preprocess_simple"
)


@dataclass(frozen=True, slots=True)
class ImagePreprocessorConfig:
    denoise_strength: int = 7
    sharpen_strength: float = 1.5
    contrast_clip_limit: float = 2.0
    morphology_kernel_size: int = 3


@dataclass(frozen=True, slots=True)
class ImagePreprocessorDependencies:
    opencv_api: OpenCVApi
    config: ImagePreprocessorConfig
    logger: StandardLogger

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ImagePreprocessorDependencies",
            config=self.config,
            logger=self.logger,
            opencv_api=self.opencv_api,
        )


class ImagePreprocessor:

    def __init__(self, deps: ImagePreprocessorDependencies) -> None:
        self._opencv_api = deps.opencv_api
        self._config = deps.config
        self._logger = deps.logger

    def _convert_to_grayscale(self, image_np: numpy.ndarray) -> numpy.ndarray:
        if len(image_np.shape) == 3:
            return self._opencv_api.cvt_color(image_np, self._opencv_api.color_rgb2gray)
        return image_np

    def detect_complexity(self, image_np: numpy.ndarray) -> tuple[bool, dict[str, float | int]]:
        metrics: dict[str, float | int] = {}
        try:
            gray = self._convert_to_grayscale(image_np)
            if gray.size < 100:
                return (False, metrics)
            variance = float(numpy.var(gray)) if gray.size > 1 else 0.0
            metrics["variance"] = variance
            edges = self._opencv_api.canny(gray, 50, 150)
            edge_density = float(numpy.count_nonzero(edges)) / float(max(edges.size, 1))
            metrics["edge_density"] = edge_density
            min_val, max_val = (float(numpy.min(gray)), float(numpy.max(gray)))
            mean_val = float(numpy.mean(gray))
            contrast_ratio = (max_val - min_val) / max(mean_val, 1.0)
            metrics["contrast_ratio"] = contrast_ratio
            _, binary = self._opencv_api.threshold(
                gray,
                0,
                255,
                self._opencv_api.thresh_binary + self._opencv_api.thresh_otsu,
            )
            contours, _ = self._opencv_api.find_contours(
                binary,
                self._opencv_api.retr_external,
                self._opencv_api.chain_approx_simple,
            )
            text_regions = sum(
                1 for contour in contours if self._opencv_api.contour_area(contour) > 50
            )
            metrics["text_regions"] = text_regions
            is_complex = (
                variance < 500
                or variance > 5000
                or edge_density > 0.15
                or (contrast_ratio < 0.3)
                or (text_regions > 20)
            )
            return (is_complex, metrics)
        except RECOVERABLE_EXCEPTIONS as error:
            log_handled_exception(
                self._logger,
                error,
                message="Complexity detection failed (non-critical).",
                operation=OPERATION_FILES_IMAGE_PREPROCESSING_DETECT_COMPLEXITY,
                level="debug",
            )
            return (False, metrics)

    def normalize_image(self, image_np: numpy.ndarray) -> numpy.ndarray:
        try:
            if len(image_np.shape) == 3:
                gray = self._opencv_api.cvt_color(image_np, self._opencv_api.color_rgb2gray)
            else:
                gray = image_np.copy()
            height, width = gray.shape[:2]
            if height < 10 or width < 10:
                return gray
            optimal_height = 2000
            if height < 800:
                scale = 2.0
            elif height > 4000:
                scale = optimal_height / height
            else:
                scale = 1.0
            if scale != 1.0:
                new_width = max(1, int(width * scale))
                new_height = max(1, int(height * scale))
                gray = self._opencv_api.resize(
                    gray,
                    (new_width, new_height),
                    interpolation=self._opencv_api.inter_cubic,
                )
            return gray
        except RECOVERABLE_EXCEPTIONS as error:
            log_handled_exception(
                self._logger,
                error,
                message="Image normalization failed (non-critical).",
                operation=OPERATION_FILES_IMAGE_PREPROCESSING_NORMALIZE_IMAGE,
                level="debug",
            )
            return self._convert_to_grayscale(image_np)

    def preprocess_simple(self, image_np: numpy.ndarray) -> numpy.ndarray:
        try:
            gray = self.normalize_image(image_np)
            blurred = self._opencv_api.gaussian_blur(gray, (0, 0), 3)
            sharpened = self._opencv_api.add_weighted(
                gray,
                self._config.sharpen_strength,
                blurred,
                -(self._config.sharpen_strength - 1),
                0,
            )
            sharpened = numpy.clip(sharpened, 0, 255).astype(numpy.uint8)
            equalized = self._opencv_api.equalize_hist(sharpened)
            return equalized
        except RECOVERABLE_EXCEPTIONS as error:
            log_handled_exception(
                self._logger,
                error,
                message="Simple preprocessing failed (non-critical).",
                operation=OPERATION_FILES_IMAGE_PREPROCESSING_PREPROCESS_SIMPLE,
                level="debug",
            )
            return self.normalize_image(image_np)

    def preprocess_complex(self, image_np: numpy.ndarray) -> list[numpy.ndarray]:
        variants: list[numpy.ndarray] = []
        gray = self.normalize_image(image_np)
        variants.append(gray)

        preprocessing_strategies = [
            (self._strategy_adaptive_threshold, "adaptive threshold"),
            (self._strategy_binary_enhancement, "binary enhancement"),
            (self._strategy_edge_preservation, "edge preservation"),
            (self._strategy_median_filter, "median filter"),
        ]

        for strategy_method, strategy_name in preprocessing_strategies:
            try:
                result = strategy_method(gray)
                if result is not None:
                    variants.append(result)
            except RECOVERABLE_EXCEPTIONS as error:
                log_handled_exception(
                    self._logger,
                    error,
                    message="Preprocessing strategy failed (non-critical).",
                    operation=OPERATION_FILES_IMAGE_PREPROCESSING_PREPROCESS_COMPLEX_STRATEGY,
                    details={"strategy": strategy_name},
                    level="debug",
                )

        return variants

    def _strategy_adaptive_threshold(self, gray: numpy.ndarray) -> numpy.ndarray:
        denoised = self._opencv_api.bilateral_filter(gray, self._config.denoise_strength, 75, 75)
        clahe = self._opencv_api.create_clahe(self._config.contrast_clip_limit, (8, 8))
        enhanced = clahe.apply(denoised)
        binary = self._opencv_api.adaptive_threshold(
            enhanced,
            255,
            self._opencv_api.adaptive_thresh_gaussian_c,
            self._opencv_api.thresh_binary,
            11,
            2,
        )
        kernel = self._opencv_api.get_structuring_element(
            self._opencv_api.morph_rect,
            (self._config.morphology_kernel_size, self._config.morphology_kernel_size),
        )
        closed = self._opencv_api.morphology_ex(binary, self._opencv_api.morph_close, kernel)
        return closed

    def _strategy_binary_enhancement(self, gray: numpy.ndarray) -> numpy.ndarray:
        denoised = self._opencv_api.fast_nl_means_denoising(gray, None, 10, 7, 21)
        _, binary = self._opencv_api.threshold(
            denoised,
            0,
            255,
            self._opencv_api.thresh_binary + self._opencv_api.thresh_otsu,
        )
        kernel = self._opencv_api.get_structuring_element(self._opencv_api.morph_rect, (2, 2))
        opened = self._opencv_api.morphology_ex(binary, self._opencv_api.morph_open, kernel)
        dilated = self._opencv_api.dilate(opened, kernel, None, (-1, -1), 1)
        return dilated

    def _strategy_edge_preservation(self, gray: numpy.ndarray) -> numpy.ndarray:
        denoised = self._opencv_api.bilateral_filter(gray, 9, 75, 75)
        clahe = self._opencv_api.create_clahe(self._config.contrast_clip_limit, (8, 8))
        enhanced = clahe.apply(denoised)
        blurred = self._opencv_api.gaussian_blur(enhanced, (9, 9), 10.0)
        sharpened = self._opencv_api.add_weighted(enhanced, 1.5, blurred, -0.5, 0)
        gamma = 1.2
        inv_gamma = 1.0 / gamma
        table = numpy.array([(level / 255.0) ** inv_gamma * 255 for level in range(256)]).astype(
            "uint8",
        )
        corrected = self._opencv_api.lookup_table(sharpened, table)
        return corrected

    def _strategy_median_filter(self, gray: numpy.ndarray) -> numpy.ndarray:
        denoised = self._opencv_api.median_blur(gray, 3)
        binary = self._opencv_api.adaptive_threshold(
            denoised,
            255,
            self._opencv_api.adaptive_thresh_mean_c,
            self._opencv_api.thresh_binary,
            15,
            10,
        )
        kernel = self._opencv_api.get_structuring_element(self._opencv_api.morph_rect, (2, 2))
        gradient = self._opencv_api.morphology_ex(binary, self._opencv_api.morph_gradient, kernel)
        inverted = self._opencv_api.bitwise_not(gradient)
        return inverted
