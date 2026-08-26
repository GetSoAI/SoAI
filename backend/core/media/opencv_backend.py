"""SoAI - Optional OpenCV media backend construction [backend/core/media/opencv_backend.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from core.imports.availability import module_available

if TYPE_CHECKING:
    from core.media.opencv_api import OpenCVApi

__all__ = ("create_optional_opencv_api",)


opencv_api_builder: Callable[[], OpenCVApi] | None
if module_available("cv2"):
    from core.media.opencv_api import build_opencv_api

    opencv_api_builder = build_opencv_api
else:
    opencv_api_builder = None


def create_optional_opencv_api() -> OpenCVApi | None:
    if opencv_api_builder is None or not module_available("cv2"):
        return None
    return opencv_api_builder()
