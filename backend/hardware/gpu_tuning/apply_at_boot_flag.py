"""SoAI - Shared apply_at_boot flag parsing for GPU slot operations [backend/hardware/gpu_tuning/apply_at_boot_flag.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_operation_results import build_gpu_operation_error
from core.validation.booleans import parse_bool

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("parse_apply_at_boot_flag_or_error",)


def parse_apply_at_boot_flag_or_error(
    *,
    device_id: str,
    slot_id: str,
    apply_at_boot: bool | None,
    default: bool | None,
) -> tuple[bool | None, JSONDict | None]:
    if apply_at_boot is None:
        return (None, None)
    try:
        return (parse_bool(apply_at_boot, default=default), None)
    except ValidationError as exception:
        return (
            None,
            build_gpu_operation_error(
                "invalid_request_error",
                str(exception),
                device_id=device_id,
                slot=slot_id,
            ),
        )
