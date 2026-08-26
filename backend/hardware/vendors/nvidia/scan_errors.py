"""SoAI - NVIDIA scan error classification [backend/hardware/vendors/nvidia/scan_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import pynvml

__all__ = (
    "is_expected_nvml_device_scan_error",
    "is_expected_nvml_unavailable_error",
)


def is_expected_nvml_device_scan_error(exception: pynvml.NVMLError) -> bool:
    try:
        invalid_argument_error = pynvml.NVMLError_InvalidArgument
    except AttributeError:
        return False
    return isinstance(invalid_argument_error, type) and isinstance(
        exception,
        invalid_argument_error,
    )


def is_expected_nvml_unavailable_error(exception: pynvml.NVMLError) -> bool:
    try:
        driver_not_loaded_error = pynvml.NVMLError_DriverNotLoaded
    except AttributeError:
        driver_not_loaded_error = None
    try:
        library_not_found_error = pynvml.NVMLError_LibraryNotFound
    except AttributeError:
        library_not_found_error = None
    if isinstance(driver_not_loaded_error, type) and isinstance(exception, driver_not_loaded_error):
        return True
    if isinstance(library_not_found_error, type) and isinstance(exception, library_not_found_error):
        return True
    expected_error_codes: list[int] = []
    try:
        driver_not_loaded_code = pynvml.NVML_ERROR_DRIVER_NOT_LOADED
    except AttributeError:
        driver_not_loaded_code = None
    if isinstance(driver_not_loaded_code, int):
        expected_error_codes.append(driver_not_loaded_code)
    try:
        library_not_found_code = pynvml.NVML_ERROR_LIBRARY_NOT_FOUND
    except AttributeError:
        library_not_found_code = None
    if isinstance(library_not_found_code, int):
        expected_error_codes.append(library_not_found_code)
    try:
        exception_value = exception.value
    except AttributeError:
        exception_value = None
    return exception_value in tuple(expected_error_codes)
