"""SoAI - Shared NVIDIA tuning error reporting [backend/hardware/vendors/nvidia/tuning_error_reporting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from hardware.result_messages import append_recoverable_exception_message

__all__ = ("report_nvidia_tuning_exception",)


def report_nvidia_tuning_exception(
    *,
    vendor_id: int,
    errors: list[str],
    exception: Exception,
    message: str,
    operation: str,
) -> None:
    append_recoverable_exception_message(
        errors,
        None,
        exception,
        message,
        operation,
        vendor_id,
    )
