"""SoAI - OpenCV API bindings for media parsing [backend/core/media/opencv_api.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

import cv2

from core.errors.exceptions import StateError

if TYPE_CHECKING:
    from cv2.typing import MatLike

__all__ = (
    "OpenCVApi",
    "build_opencv_api",
)


@dataclass(frozen=True, slots=True)
class OpenCVApi:
    cvt_color: Callable[..., MatLike]
    color_rgb2gray: int
    canny: Callable[..., MatLike]
    threshold: Callable[..., tuple[float, MatLike]]
    thresh_binary: int
    thresh_otsu: int
    find_contours: Callable[..., tuple[Sequence[MatLike], MatLike]]
    retr_external: int
    chain_approx_simple: int
    contour_area: Callable[..., float]
    resize: Callable[..., MatLike]
    inter_cubic: int
    gaussian_blur: Callable[..., MatLike]
    add_weighted: Callable[..., MatLike]
    equalize_hist: Callable[..., MatLike]
    bilateral_filter: Callable[..., MatLike]
    create_clahe: Callable[..., cv2.CLAHE]
    adaptive_threshold: Callable[..., MatLike]
    adaptive_thresh_gaussian_c: int
    adaptive_thresh_mean_c: int
    get_structuring_element: Callable[..., MatLike]
    morph_rect: int
    morph_close: int
    morph_open: int
    morph_gradient: int
    morphology_ex: Callable[..., MatLike]
    fast_nl_means_denoising: Callable[..., MatLike]
    dilate: Callable[..., MatLike]
    lookup_table: Callable[..., MatLike]
    median_blur: Callable[..., MatLike]
    bitwise_not: Callable[..., MatLike]
    video_capture: Callable[..., cv2.VideoCapture]
    cap_prop_frame_width: int
    cap_prop_frame_height: int
    cap_prop_fps: int
    cap_prop_frame_count: int
    cap_prop_fourcc: int


def _require_int_value(value: float | str | bool | None, attribute: str) -> int:
    if not isinstance(value, int):
        raise StateError(f"OpenCV attribute {attribute} is missing or invalid.")
    return value


def _require_callable_value[T](value: T, attribute: str) -> T:
    if not callable(value):
        raise StateError(f"OpenCV member {attribute} is missing or invalid.")
    return value


def build_opencv_api() -> OpenCVApi:
    try:
        cvt_color = _require_callable_value(cv2.cvtColor, "cvtColor")
        canny = _require_callable_value(cv2.Canny, "Canny")
        threshold = _require_callable_value(cv2.threshold, "threshold")
        find_contours = _require_callable_value(cv2.findContours, "findContours")
        contour_area = _require_callable_value(cv2.contourArea, "contourArea")
        resize = _require_callable_value(cv2.resize, "resize")
        gaussian_blur = _require_callable_value(cv2.GaussianBlur, "GaussianBlur")
        add_weighted = _require_callable_value(cv2.addWeighted, "addWeighted")
        equalize_hist = _require_callable_value(cv2.equalizeHist, "equalizeHist")
        bilateral_filter = _require_callable_value(cv2.bilateralFilter, "bilateralFilter")
        create_clahe = _require_callable_value(cv2.createCLAHE, "createCLAHE")
        adaptive_threshold = _require_callable_value(cv2.adaptiveThreshold, "adaptiveThreshold")
        get_structuring_element = _require_callable_value(
            cv2.getStructuringElement,
            "getStructuringElement",
        )
        morphology_ex = _require_callable_value(cv2.morphologyEx, "morphologyEx")
        fast_nl_means_denoising = _require_callable_value(
            cv2.fastNlMeansDenoising,
            "fastNlMeansDenoising",
        )
        dilate = _require_callable_value(cv2.dilate, "dilate")
        lookup_table = _require_callable_value(cv2.LUT, "LUT")
        median_blur = _require_callable_value(cv2.medianBlur, "medianBlur")
        bitwise_not = _require_callable_value(cv2.bitwise_not, "bitwise_not")
        video_capture = _require_callable_value(cv2.VideoCapture, "VideoCapture")

        color_rgb2gray = _require_int_value(cv2.COLOR_RGB2GRAY, "COLOR_RGB2GRAY")
        thresh_binary = _require_int_value(cv2.THRESH_BINARY, "THRESH_BINARY")
        thresh_otsu = _require_int_value(cv2.THRESH_OTSU, "THRESH_OTSU")
        retr_external = _require_int_value(cv2.RETR_EXTERNAL, "RETR_EXTERNAL")
        chain_approx_simple = _require_int_value(cv2.CHAIN_APPROX_SIMPLE, "CHAIN_APPROX_SIMPLE")
        inter_cubic = _require_int_value(cv2.INTER_CUBIC, "INTER_CUBIC")
        adaptive_thresh_gaussian_c = _require_int_value(
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            "ADAPTIVE_THRESH_GAUSSIAN_C",
        )
        adaptive_thresh_mean_c = _require_int_value(
            cv2.ADAPTIVE_THRESH_MEAN_C,
            "ADAPTIVE_THRESH_MEAN_C",
        )
        morph_rect = _require_int_value(cv2.MORPH_RECT, "MORPH_RECT")
        morph_close = _require_int_value(cv2.MORPH_CLOSE, "MORPH_CLOSE")
        morph_open = _require_int_value(cv2.MORPH_OPEN, "MORPH_OPEN")
        morph_gradient = _require_int_value(cv2.MORPH_GRADIENT, "MORPH_GRADIENT")
        cap_prop_frame_width = _require_int_value(cv2.CAP_PROP_FRAME_WIDTH, "CAP_PROP_FRAME_WIDTH")
        cap_prop_frame_height = _require_int_value(
            cv2.CAP_PROP_FRAME_HEIGHT,
            "CAP_PROP_FRAME_HEIGHT",
        )
        cap_prop_fps = _require_int_value(cv2.CAP_PROP_FPS, "CAP_PROP_FPS")
        cap_prop_frame_count = _require_int_value(cv2.CAP_PROP_FRAME_COUNT, "CAP_PROP_FRAME_COUNT")
        cap_prop_fourcc = _require_int_value(cv2.CAP_PROP_FOURCC, "CAP_PROP_FOURCC")
    except AttributeError as exception:
        raise StateError("OpenCV is missing required members.") from exception
    return OpenCVApi(
        cvt_color=cvt_color,
        color_rgb2gray=color_rgb2gray,
        canny=canny,
        threshold=threshold,
        thresh_binary=thresh_binary,
        thresh_otsu=thresh_otsu,
        find_contours=find_contours,
        retr_external=retr_external,
        chain_approx_simple=chain_approx_simple,
        contour_area=contour_area,
        resize=resize,
        inter_cubic=inter_cubic,
        gaussian_blur=gaussian_blur,
        add_weighted=add_weighted,
        equalize_hist=equalize_hist,
        bilateral_filter=bilateral_filter,
        create_clahe=create_clahe,
        adaptive_threshold=adaptive_threshold,
        adaptive_thresh_gaussian_c=adaptive_thresh_gaussian_c,
        adaptive_thresh_mean_c=adaptive_thresh_mean_c,
        get_structuring_element=get_structuring_element,
        morph_rect=morph_rect,
        morph_close=morph_close,
        morph_open=morph_open,
        morph_gradient=morph_gradient,
        morphology_ex=morphology_ex,
        fast_nl_means_denoising=fast_nl_means_denoising,
        dilate=dilate,
        lookup_table=lookup_table,
        median_blur=median_blur,
        bitwise_not=bitwise_not,
        video_capture=video_capture,
        cap_prop_frame_width=cap_prop_frame_width,
        cap_prop_frame_height=cap_prop_frame_height,
        cap_prop_fps=cap_prop_fps,
        cap_prop_frame_count=cap_prop_frame_count,
        cap_prop_fourcc=cap_prop_fourcc,
    )
